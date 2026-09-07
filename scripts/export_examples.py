#!/usr/bin/env python3
"""Make a readable Markdown catalog of public development questions and answer keys."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from puzzles.suite import verify_question


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, nargs="+", required=True)
    parser.add_argument("--difficulty", choices=["hard", "extreme"], default="extreme")
    parser.add_argument("--out", type=Path, default=Path("docs/challenge-examples.md"))
    args = parser.parse_args(argv)
    chosen = {}
    for path in args.questions:
        for question in json.loads(path.read_text())["questions"]:
            if question["difficulty"] == args.difficulty and question["family"] not in chosen:
                verify_question(question)
                chosen[question["family"]] = question
    if not chosen:
        parser.error("no matching questions")
    parts = ["# Challenge examples", "One public development example per family. These are structural "
             f"`{args.difficulty}` settings; current model failure rates are unmeasured. "
             "Reference answers are collapsed below each puzzle. For API evaluation, preserve "
             "the separate system message where shown. See [the guide](hard-suite.md) for the protocol."]
    for family, q in chosen.items():
        title, body = q["prompt"].split("\n", 1)
        parts += [f"## {title}", f"Family: `{family}` · ID: `{q['id']}`"]
        if q.get("system_prompt"):
            parts += ["### Authoritative rules (system message)", q["system_prompt"], "### Puzzle (user message)"]
        parts.append(body)
        parts.append("<details>\n<summary>Reference answer</summary>\n\n```json\n"
                     + json.dumps({"answer": q["answer"]}, indent=2) + "\n```\n\n</details>")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n\n".join(parts) + "\n")
    print(f"Exported {len(chosen)} examples to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
