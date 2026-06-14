import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import product
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from models import resolve_models


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_QUESTIONS = "questions/math-scramble-puzzles.json"

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
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("questions"), list):
        raise ValueError(
            "structured question files must contain a top-level questions list; "
            "use word_unscramble.py for word-map files"
        )

    prompt_template = data.get("prompt_template")

    questions = []
    for i, item in enumerate(data["questions"]):
        prompt = item.get("prompt")
        if not prompt:
            if not prompt_template:
                raise ValueError("questions need either a prompt or top-level prompt_template")
            prompt = prompt_template.format(
                scrambled=item["scrambled"],
                task=item.get("task", ""),
            )

        questions.append({
            "id": item.get("id", i),
            "scrambled": item["scrambled"],
            "prompt": prompt,
            "answer": item["answer"],
        })

    return questions


def is_correct(parsed, expected):
    if not parsed:
        return False

    if expected == parsed:
        return True

    if len(parsed) != len(expected):
        return False

    def normalized_words(text):
        normalized = re.sub(r"\s+", " ", str(text).strip().lower())
        return sorted(normalized.split())

    if normalized_words(parsed) == normalized_words(expected):
        return True

    return False

def call_openrouter(api_key, payload, timeout):
    started = time.perf_counter()
    result = subprocess.run(
        [
            "curl",
            "-sS",
            "--max-time",
            str(timeout),
            "-X",
            "POST",
            OPENROUTER_URL,
            "-H",
            f"Authorization: Bearer {api_key}",
            "-H",
            "Content-Type: application/json",
            "-H",
            "HTTP-Referer: https://github.com/local/unscramble-bench",
            "-H",
            "X-Title: unscramble-bench unscrambling benchmark",
            "--data-binary",
            "@-",
        ],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8").strip() or f"curl exit {result.returncode}")
    result = json.loads(result.stdout.decode("utf-8"))
    return result, time.perf_counter() - started

def run_attempt(api_key, model, config, run, question, timeout):
    try:
        options = CONFIGS[config]
        payload = {
            "model": model,
            "max_tokens": options["max_tokens"],
            "reasoning": options["reasoning"],
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "user", "content": question["prompt"]},
            ],
        }
        response, latency = call_openrouter(api_key, payload, timeout)
        return score_attempt(model, config, run, question, response, latency, None)
    except Exception as exc:
        return score_attempt(model, config, run, question, None, 0.0, str(exc))


def score_attempt(model, config, run, question, response, latency, error):
    raw = None
    parsed = None

    if response:
        if "error" in response:
            error = response["error"].get("message", response["error"])
        else:
            raw = response["choices"][0]["message"]["content"]
            try:
                parsed = str(json.loads(raw)["answer"])
            except (KeyError, TypeError, json.JSONDecodeError) as exc:
                error = f"parse error: {exc}"

    correct = is_correct(parsed, question["answer"])

    return {
        "model": model,
        "response_model": response.get("model") if response else None,
        "config": config,
        "run": run,
        "problem_id": question["id"],
        "prompt": question["prompt"],
        "expected_answer": question["answer"],
        "raw_response": raw,
        "parsed_answer": parsed,
        "correct": correct,
        "latency_seconds": round(latency, 3),
        "usage": response.get("usage") if response else None,
        "error": error,
    }


def aggregate(rows):
    scores = defaultdict(Counter)
    for row in rows:
        score = scores[row["model"], row["config"]]
        score["correct"] += row["correct"]
        score["total"] += 1
        score["failed_api_calls"] += row["raw_response"] is None and bool(row["error"])

    return [
        {
            "model": model,
            "config": config,
            "correct": score["correct"],
            "total": score["total"],
            "percent": round(100 * score["correct"] / score["total"], 2),
            "failed_api_calls": score["failed_api_calls"],
        }
        for (model, config), score in scores.items()
    ]


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
        default=f"runs/{default_out_prefix}-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.json",
    )
    parser.add_argument("--models", default="all")
    parser.add_argument("--configs", default="all")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--workers", type=int, default=32)
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
    ):
        print("Error: --runs, --limit, --timeout, and --workers must be positive", file=sys.stderr)
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

    questions = questions[: args.limit]
    models = resolve_models(args.models)

    if not questions or not models or not configs:
        print("Error: questions, models, and configs must be non-empty", file=sys.stderr)
        return 1

    tasks = list(product(models, configs, range(1, args.runs + 1), questions))

    total_tasks = len(tasks)
    rows = [None] * total_tasks
    max_workers = min(args.workers, total_tasks)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {
            executor.submit(
                run_attempt,
                api_key,
                model,
                config,
                run,
                question,
                args.timeout,
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

    results = {
        "metadata": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "openrouter_url": OPENROUTER_URL,
            "args": vars(args),
            "question_file": args.questions,
            "total_questions": len(questions),
            "models": models,
            "configs": configs,
            "runs": args.runs,
        },
        "aggregates": aggregate(rows),
        "results": rows,
    }

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")

    print(f"\nSaved results to {output}")
    for score in results["aggregates"]:
        print(
            f"- {score['model']} [{score['config']}]: "
            f"{score['correct']}/{score['total']} ({score['percent']}%), "
            f"failed API calls={score['failed_api_calls']}"
        )
    return 0


def main(argv=None):
    args = parse_args(
        argv or sys.argv[1:],
        description="Run the math scramble benchmark.",
        default_questions=DEFAULT_QUESTIONS,
        default_out_prefix="scramble-results",
    )
    questions = load_questions(args.questions)
    return run_benchmark(args, questions)


if __name__ == "__main__":
    main()
