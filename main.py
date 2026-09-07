import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import product
import json
import hashlib
import math
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter

from error_utils import (
    BenchmarkApiError,
    is_internal_server_error_response,
    response_error_message,
)
from models import resolve_models


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_QUESTIONS = "questions/math-scramble-puzzles.json"

CONNECT_TIMEOUT = 10  # seconds to establish the TCP/TLS connection
MAX_API_RETRIES = 3
DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "HTTP-Referer": "https://github.com/zwiesenthal/unscramble-bench",
    "X-Title": "unscramble-bench unscrambling benchmark",
}
JSON_FENCE_RE = re.compile(
    r"^\s*```(?:json)?\s*(.*?)\s*```\s*$",
    re.IGNORECASE | re.DOTALL,
)
REASONING_FIELD_NAMES = (
    "reasoning",
    "reasoning_details",
    "reasoning_content",
    "thinking",
    "thoughts",
)


CONFIGS = {
    "low": {
        "reasoning": {"enabled": True, "effort": "low"},
        "max_tokens": 4_096,
    },
    "high": {
        "reasoning": {"enabled": True, "effort": "high"},
        "max_tokens": 32_768,
    },
}


def load_questions(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"),
                      object_pairs_hook=unique_json_object, parse_constant=reject_json_constant,
                      parse_float=finite_json_float)
    if not isinstance(data, dict) or not isinstance(data.get("questions"), list):
        raise ValueError(
            "structured question files must contain a top-level questions list; "
            "use word_unscramble.py for word-map files"
        )

    prompt_template = data.get("prompt_template")
    if prompt_template is not None and not isinstance(prompt_template, str):
        raise ValueError("prompt_template must be a string when present")

    questions = []
    seen_ids = set()
    for i, item in enumerate(data["questions"]):
        if not isinstance(item, dict):
            raise ValueError(f"questions[{i}] must be an object")
        if "answer" not in item:
            raise ValueError(f"questions[{i}] is missing required field 'answer'")

        question_id = item.get("id", i)
        question_id_key = str(question_id)
        if question_id_key in seen_ids:
            raise ValueError(f"duplicate question id: {question_id!r}")
        seen_ids.add(question_id_key)

        prompt = item.get("prompt")
        if not prompt:
            if not prompt_template:
                raise ValueError(
                    f"questions[{i}] needs either a prompt or top-level prompt_template"
                )
            try:
                prompt = prompt_template.format(**item)
            except KeyError as exc:
                missing = exc.args[0]
                raise ValueError(
                    f"questions[{i}] cannot fill prompt_template; missing field {missing!r}"
                ) from exc

        scrambled = item.get("scrambled", "")
        phrase = item.get("phrase")
        if scrambled and phrase:
            if sorted(str(scrambled).replace(" ", "")) != sorted(str(phrase).replace(" ", "")):
                raise ValueError(
                    f"questions[{i}] ({question_id!r}): scrambled letters are not "
                    f"an anagram of the phrase {phrase!r}"
                )

        scoring = item.get("scoring", data.get("scoring", "legacy"))
        if scoring not in ("legacy", "json"):
            raise ValueError(f"questions[{i}]: unknown scoring mode {scoring!r}")
        system_prompt = item.get("system_prompt", data.get("system_prompt"))
        if system_prompt is not None and not isinstance(system_prompt, str):
            raise ValueError(f"questions[{i}]: system_prompt must be a string")
        if not isinstance(prompt, str):
            raise ValueError(f"questions[{i}]: prompt must be a string")
        if scoring == "json":
            # Reject NaN / Infinity in reference answers too.
            json.dumps(item["answer"], allow_nan=False)
        question = {
            "id": question_id,
            "scrambled": scrambled,
            "prompt": prompt,
            "answer": item["answer"] if scoring == "json" else str(item["answer"]),
            "scoring": scoring,
        }
        if system_prompt:
            question["system_prompt"] = system_prompt
        for key in ("family", "difficulty", "split", "seed", "version", "instance_hash"):
            if key in item:
                question[key] = item[key]
        if scoring == "json" and "instance" in item:
            question["instance"] = item["instance"]  # Grader-only; question_messages uses an allowlist.
        questions.append(question)

    return questions


def normalize_text(text):
    return re.sub(r"\s+", " ", str(text).strip().lower())


def normalized_words(text):
    return normalize_text(text).split()


def is_correct(parsed, expected):
    if parsed is None:
        return False

    if str(expected) == str(parsed):
        return True

    if normalize_text(parsed) == normalize_text(expected):
        return True

    return sorted(normalized_words(parsed)) == sorted(normalized_words(expected))


def exact_json_equal(actual, expected):
    """JSON object order is irrelevant; array order and scalar types are exact."""
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            exact_json_equal(actual[k], expected[k]) for k in expected
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            exact_json_equal(a, b) for a, b in zip(actual, expected)
        )
    return actual == expected


def unique_json_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate JSON key: {key!r}")
        out[key] = value
    return out


def reject_json_constant(value):
    raise ValueError(f"non-finite JSON number: {value}")


def finite_json_float(value):
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite JSON number: {value}")
    return parsed


def parse_model_answer(raw, native=False):
    """Read the {"answer": ...} object returned by a model."""
    if raw is None:
        raise ValueError("empty response content")

    text = str(raw).strip()
    fence = JSON_FENCE_RE.match(text)
    if fence:
        text = fence.group(1).strip()

    data = json.loads(text, object_pairs_hook=unique_json_object,
                      parse_constant=reject_json_constant, parse_float=finite_json_float)
    if not isinstance(data, dict):
        raise ValueError("response JSON must be an object")
    if "answer" not in data:
        raise KeyError("answer")
    if native and set(data) != {"answer"}:
        raise ValueError("response JSON must have exactly one key: answer")
    return data["answer"] if native else str(data["answer"])


def question_messages(question):
    """Only these two explicit fields are sent to a model; never the answer key."""
    messages = []
    if question.get("system_prompt"):
        messages.append({"role": "system", "content": question["system_prompt"]})
    messages.append({"role": "user", "content": question["prompt"]})
    return messages


def prompt_hash(question):
    payload = json.dumps(question_messages(question), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def retry_delay_seconds(attempt_index):
    return min(2 ** attempt_index, 8)


def response_choice_and_message(response):
    try:
        choices = response["choices"]
        if not choices:
            return None, None, "malformed response: empty choices"
        choice = choices[0]
        message = choice["message"]
    except (KeyError, IndexError, TypeError) as exc:
        return None, None, f"malformed response: {exc}"

    if not isinstance(choice, dict):
        return None, None, f"malformed response: choice is {type(choice).__name__}"
    if not isinstance(message, dict):
        return choice, None, f"malformed response: message is {type(message).__name__}"

    return choice, message, None


def response_message_content(response):
    _choice, message, error = response_choice_and_message(response)
    if error:
        return None, error

    try:
        content = message["content"]
    except KeyError as exc:
        return None, f"malformed response: {exc}"

    if content is None:
        return None, "malformed response: empty message content"
    return str(content), None


def extract_reasoning_fields(response):
    choice, message, error = response_choice_and_message(response)
    if error:
        return None, None, None

    reasoning = {}
    for label, container in (("message", message), ("choice", choice)):
        for field in REASONING_FIELD_NAMES:
            if field in container:
                reasoning[f"{label}.{field}"] = container[field]

    return message, choice, reasoning or None


def build_session(api_key, pool_size):
    """A connection-pooled session.

    Sized so every worker thread can hold a keep-alive connection without
    contention, instead of paying a fresh TCP/TLS handshake per request.
    """
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    session.headers["Authorization"] = f"Bearer {api_key}"

    adapter = HTTPAdapter(
        pool_connections=pool_size,
        pool_maxsize=pool_size,
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def call_openrouter(session, payload, timeout):
    started = time.perf_counter()
    try:
        response = session.post(
            OPENROUTER_URL,
            json=payload,
            timeout=(CONNECT_TIMEOUT, timeout),
        )
    except requests.RequestException as exc:
        raise BenchmarkApiError(str(exc), retryable=True) from exc

    elapsed = time.perf_counter() - started
    try:
        body = response.json()
    except ValueError as exc:
        message = f"HTTP {response.status_code}: non-JSON response: {response.text[:200]}"
        raise BenchmarkApiError(
            message,
            retryable=response.status_code == 429 or response.status_code >= 500,
        ) from exc

    # OpenRouter reports errors both via HTTP status and as an error object in
    # a 200 body; classify from the status here and let score_attempt handle
    # error bodies that arrive with a 200.
    if response.status_code >= 400:
        detail = response_error_message(body) or response.text[:200]
        raise BenchmarkApiError(
            f"HTTP {response.status_code}: {detail}",
            retryable=response.status_code == 429 or response.status_code >= 500,
        )
    return body, elapsed


def run_attempt(session, model, config, run, question, timeout, max_tokens):
    total_latency = 0.0
    try:
        options = CONFIGS[config]
        payload = {
            "model": model,
            "max_tokens": max_tokens or options["max_tokens"],
            "reasoning": options["reasoning"],
            "response_format": {"type": "json_object"},
            "messages": question_messages(question),
        }

        for attempt_index in range(MAX_API_RETRIES + 1):
            try:
                response, latency = call_openrouter(session, payload, timeout)
                total_latency += latency
            except BenchmarkApiError as exc:
                if exc.retryable and attempt_index < MAX_API_RETRIES:
                    time.sleep(retry_delay_seconds(attempt_index))
                    continue
                return score_attempt(
                    model,
                    config,
                    run,
                    question,
                    None,
                    total_latency,
                    str(exc),
                    api_error=True,
                )
            if (
                is_internal_server_error_response(response)
                and attempt_index < MAX_API_RETRIES
            ):
                time.sleep(retry_delay_seconds(attempt_index))
                continue

            return score_attempt(
                model,
                config,
                run,
                question,
                response,
                total_latency,
                None,
                api_error=is_internal_server_error_response(response),
            )
    except Exception as exc:
        return score_attempt(
            model,
            config,
            run,
            question,
            None,
            total_latency,
            str(exc),
            api_error=False,
        )


def score_attempt(model, config, run, question, response, latency, error, api_error=False):
    raw = None
    parsed = None
    usage = response.get("usage") if isinstance(response, dict) else None
    cost = usage.get("cost") if isinstance(usage, dict) else None
    response_message = None
    response_choice = None
    reasoning = None

    if response is not None:
        response_error = response_error_message(response)
        if response_error:
            # An error body means the provider produced no model answer, so
            # count it as an API failure rather than a wrong answer.
            error = response_error
            api_error = True
        else:
            response_message, response_choice, reasoning = extract_reasoning_fields(response)
            raw, content_error = response_message_content(response)
            if content_error:
                error = content_error
            else:
                try:
                    parsed = parse_model_answer(raw, native=question.get("scoring") == "json")
                except (KeyError, TypeError, ValueError, RecursionError) as exc:
                    error = f"parse error: {exc}"

    scoring = question.get("scoring", "legacy")
    correct = (exact_json_equal(parsed, question["answer"]) if scoring == "json"
               else is_correct(parsed, question["answer"]))
    # Even a null expected answer must never turn a parse/API failure into a pass.
    correct = bool(correct and not error and not api_error)
    fields = {}
    if scoring == "json" and isinstance(question["answer"], dict):
        fields = {k: bool(not error and not api_error and isinstance(parsed, dict) and k in parsed
                          and exact_json_equal(parsed[k], v))
                  for k, v in question["answer"].items()}
    diagnostics = {}
    if scoring == "json" and not error and not api_error:
        from puzzles.assessment import diagnose
        diagnostics = diagnose(question, parsed)

    return {
        "model": model,
        "response_model": response.get("model") if isinstance(response, dict) else None,
        "config": config,
        "run": run,
        "problem_id": question["id"],
        "prompt": question["prompt"],
        "system_prompt": question.get("system_prompt"),
        "prompt_hash": prompt_hash(question),
        "scoring": scoring,
        "family": question.get("family"),
        "difficulty": question.get("difficulty"),
        "split": question.get("split"),
        "seed": question.get("seed"),
        "version": question.get("version"),
        "instance_hash": question.get("instance_hash"),
        "expected_answer": question["answer"],
        "raw_response": raw,
        "parsed_answer": parsed,
        "reasoning": reasoning,
        "response_message": response_message,
        "response_choice": response_choice,
        "correct": correct,
        "fields_correct": fields,
        "diagnostics": diagnostics,
        "latency_seconds": round(latency, 3),
        "cost": cost,
        "usage": usage,
        "error": error,
        "api_error": bool(api_error),
    }


def aggregate(rows):
    scores = defaultdict(Counter)
    for row in rows:
        score = scores[row["model"], row["config"]]
        score["correct"] += row["correct"]
        score["total"] += 1
        score["failed_api_calls"] += bool(row.get("api_error"))
        score["response_errors"] += bool(row.get("error")) and not row.get("api_error", False)
        contract = row.get("diagnostics", {}).get("contract_satisfied")
        if type(contract) is bool:
            score["assessed_contract_attempts"] += 1
            score["contract_violations"] += not contract
        if row["cost"] is not None:
            score["cost"] += row["cost"]
            score["cost_reported_attempts"] += 1

    return [
        {
            "model": model,
            "config": config,
            "correct": score["correct"],
            "total": score["total"],
            "percent": round(100 * score["correct"] / score["total"], 2),
            "failed_api_calls": score["failed_api_calls"],
            "response_errors": score["response_errors"],
            "assessed_contract_attempts": score["assessed_contract_attempts"],
            "contract_violations": score["contract_violations"],
            "non_api_attempts": score["total"] - score["failed_api_calls"],
            "percent_excluding_api_failures": (
                round(100 * score["correct"] / (score["total"] - score["failed_api_calls"]), 2)
                if score["total"] > score["failed_api_calls"] else None
            ),
            "cost": round(score["cost"], 6) if score["cost_reported_attempts"] == score["total"] else None,
            "known_cost": round(score["cost"], 6),
            "cost_missing_attempts": score["total"] - score["cost_reported_attempts"],
        }
        for (model, config), score in scores.items()
    ]


def aggregate_families(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row.get("family"), row.get("difficulty")].append(row)
    return [{"family": family, "difficulty": difficulty, **score}
            for (family, difficulty), group in groups.items() for score in aggregate(group)]


def run_timestamp():
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d-%H-%M") + f"-{now.microsecond // 1000:03d}"


def parse_args(
    argv,
    description,
    default_questions,
    default_out_prefix,
):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--questions", default=default_questions)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument(
        "--out",
        default=f"runs/{default_out_prefix}/{run_timestamp()}.json",
    )
    parser.add_argument(
        "--models",
        help="model id, comma-separated list, or group name "
        "(frontier, cheap, free, all); required unless --validate-only",
    )
    parser.add_argument("--configs", default="all")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--families", help="comma-separated family names to select before --limit")
    parser.add_argument("--difficulty", choices=["hard", "extreme"])
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--workers", type=int, default=32)
    parser.add_argument("--max-tokens", type=int)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="load and validate the question file without making API calls",
    )
    return parser.parse_args(argv)


def resolve_configs(value):
    if value == "all":
        return list(CONFIGS), None

    configs = []
    for name in value.split(","):
        name = name.strip()
        if not name:
            continue
        if name not in CONFIGS:
            return None, name
        configs.append(name)
    return list(dict.fromkeys(configs)), None


def load_env_file(path=".env"):
    env = Path(path)
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def run_benchmark(args, questions):
    if (
        args.runs < 1
        or (args.limit is not None and args.limit < 1)
        or args.timeout <= 0
        or args.workers < 1
        or (args.max_tokens is not None and args.max_tokens < 1)
    ):
        print(
            "Error: --runs, --limit, --timeout, --workers, and --max-tokens must be positive",
            file=sys.stderr,
        )
        return 1

    if args.families:
        names = set(args.families.split(","))
        unknown = names - {q.get("family") for q in questions}
        if unknown:
            print(f"Error: unknown families: {', '.join(sorted(unknown))}", file=sys.stderr)
            return 1
        questions = [q for q in questions if q.get("family") in names]
    if args.difficulty:
        questions = [q for q in questions if q.get("difficulty") == args.difficulty]
    questions = questions[: args.limit]

    if args.validate_only:
        if not questions:
            print("Error: question file must contain at least one question", file=sys.stderr)
            return 1
        print(f"Validated {len(questions)} questions from {args.questions}")
        return 0

    if not args.models:
        print(
            "Error: --models is required (model id, comma-separated list, or "
            "group name: frontier, cheap, free, all)",
            file=sys.stderr,
        )
        return 1

    configs, invalid_config = resolve_configs(args.configs)
    if invalid_config:
        print(f"Error: invalid config '{invalid_config}'. Valid configs: {', '.join(CONFIGS)}", file=sys.stderr)
        return 1

    load_env_file()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("Error: OPENROUTER_API_KEY is required in the environment", file=sys.stderr)
        return 1

    models = resolve_models(args.models)

    if not questions or not models or not configs:
        print("Error: questions, models, and configs must be non-empty", file=sys.stderr)
        return 1

    tasks = list(product(models, configs, range(1, args.runs + 1), questions))

    total_tasks = len(tasks)
    rows = [None] * total_tasks
    max_workers = min(args.workers, total_tasks)
    session = build_session(api_key, pool_size=max_workers)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {
            executor.submit(
                run_attempt,
                session,
                model,
                config,
                run,
                question,
                args.timeout,
                args.max_tokens,
            ): index
            for index, (model, config, run, question) in enumerate(tasks)
        }
        completed = 0
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            rows[index] = future.result()
            completed += 1
            row = rows[index]
            print(f"[{completed}/{total_tasks}] done {row['model']} {row['config']} run={row['run']}")

    aggregates = aggregate(rows)
    total_cost = round(sum(row["cost"] or 0 for row in rows), 6)
    missing_costs = sum(row["cost"] is None for row in rows)

    results = {
        "metadata": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "openrouter_url": OPENROUTER_URL,
            "args": vars(args),
            "question_file": args.questions,
            "question_file_sha256": hashlib.sha256(Path(args.questions).read_bytes()).hexdigest(),
            "tools_allowed": False,
            "total_questions": len(questions),
            "models": models,
            "configs": configs,
            "runs": args.runs,
            "cost": total_cost if not missing_costs else None,
            "known_cost": total_cost,
            "cost_missing_attempts": missing_costs,
        },
        "aggregates": aggregates,
        "by_family": aggregate_families(rows),
        "results": rows,
    }

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")

    print(f"\nSaved results to {output}")
    print(f"Known reported cost=${total_cost:.6f}; attempts with unknown cost={missing_costs}")
    for score in results["aggregates"]:
        cost_text = f"${score['cost']:.6f}" if score["cost"] is not None else "unknown"
        print(
            f"- {score['model']} [{score['config']}]: "
            f"{score['correct']}/{score['total']} ({score['percent']}%), "
            f"failed API calls={score['failed_api_calls']}, "
            f"cost={cost_text}"
        )
    return 0


def main(argv=None):
    args = parse_args(
        sys.argv[1:] if argv is None else argv,
        description="Run the math scramble benchmark.",
        default_questions=DEFAULT_QUESTIONS,
        default_out_prefix="scramble-results",
    )
    try:
        questions = load_questions(args.questions)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return run_benchmark(args, questions)


if __name__ == "__main__":
    sys.exit(main())
