#!/usr/bin/env python3
"""Score externally collected raw responses with the same scorer as the API runner.

Each JSONL row is {"id": question_id, "response": "raw model response"}.
Missing answers score zero; duplicate or unknown IDs are errors, never silently
discarded. This supports a separate, isolated model environment with public prompts.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main as benchmark


def score_records(questions, records, model="external"):
    known = {str(q["id"]): q for q in questions}
    if len(known) != len(questions):
        raise ValueError("duplicate question IDs")
    indexed = {}
    for record in records:
        if not isinstance(record, dict) or "id" not in record or not isinstance(record.get("response"), str):
            raise ValueError("each submission needs id and a raw response string")
        key = str(record["id"])
        if key not in known:
            raise ValueError(f"unknown question ID: {key}")
        if key in indexed:
            raise ValueError(f"duplicate submission ID: {key}")
        if "prompt_hash" in record and record["prompt_hash"] != benchmark.prompt_hash(known[key]):
            raise ValueError(f"prompt hash mismatch: {key}")
        indexed[key] = record
    rows = []
    for q in questions:
        record = indexed.get(str(q["id"]))
        response = {"choices": [{"message": {"content": record["response"]}}]} if record else None
        row = benchmark.score_attempt(model, "external", 1, q, response, 0,
                                      None if record else "missing submission")
        # Runtime/cost are unknown for externally supplied text; never invent zeros.
        row["latency_seconds"] = None
        row["missing_submission"] = record is None
        rows.append(row)
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--answers", type=Path, required=True)
    parser.add_argument("--model", default="external")
    parser.add_argument("--tool-access", choices=["none", "code", "other", "unknown"], default="unknown")
    parser.add_argument("--out", type=Path, default=Path("runs/external-results.json"))
    args = parser.parse_args(argv)
    questions = benchmark.load_questions(args.questions)
    if not questions:
        parser.error("question set is empty")
    records = [json.loads(line, object_pairs_hook=benchmark.unique_json_object,
                          parse_constant=benchmark.reject_json_constant)
               for line in args.answers.read_text().splitlines() if line.strip()]
    rows = score_records(questions, records, args.model)
    report = {"metadata": {"created_at": datetime.now(timezone.utc).isoformat(),
                            "protocol": "external responses; tool access self-reported",
                            "tool_access": args.tool_access,
                            "question_file_sha256": hashlib.sha256(args.questions.read_bytes()).hexdigest(),
                            "answers_file_sha256": hashlib.sha256(args.answers.read_bytes()).hexdigest()},
              "aggregates": benchmark.aggregate(rows), "by_family": benchmark.aggregate_families(rows),
              "results": rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    summary = report["aggregates"][0]
    print(f"{summary['correct']}/{summary['total']} correct ({summary['percent']}%). Saved {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
