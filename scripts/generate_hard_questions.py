#!/usr/bin/env python3
"""Generate reproducible, exact-verifiable puzzles; no API key or extra dependencies."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from puzzles.common import LEVELS, SPLITS, VERSION
from puzzles.suite import FAMILIES, GROUPS, build_question, public_question, verify_question


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--families", default="all", help="puzzles, alignment, all, or comma-separated names")
    parser.add_argument("--difficulty", choices=["all", *LEVELS], default="all")
    parser.add_argument("--split", choices=SPLITS, default="dev")
    parser.add_argument("--seed", type=int, default=0, help="first seed; increments for each case")
    parser.add_argument("--count", type=int, default=4, help="questions PER family PER difficulty")
    parser.add_argument("--selection", type=Path, help="optional JSON mapping family -> difficulty -> seed list")
    parser.add_argument("--out", type=Path, default=Path("questions/hard-reasoning.json"))
    parser.add_argument("--public-out", type=Path, help="write only model-visible prompts to this JSONL file")
    parser.add_argument("--check", type=Path, help="verify this existing generated file instead of generating")
    parser.add_argument("--regenerate", action="store_true", help="with --check, also reproduce every instance from its seed")
    args = parser.parse_args(argv)
    if args.check:
        from main import load_questions
        loaded = load_questions(args.check)  # Shared shape / ID / scoring validation.
        data = json.loads(args.check.read_text())
        if not loaded:
            parser.error("question file is empty")
        for question in data["questions"]:
            verify_question(question, regenerate=args.regenerate)
        print(f"Verified {len(loaded)} prompts, rules, hashes and reference answers from {args.check}")
        return 0
    if args.regenerate:
        parser.error("--regenerate requires --check")
    if args.count < 1 or args.seed < 0:
        parser.error("count must be positive and seed must be nonnegative")
    if args.public_out and args.public_out.resolve() == args.out.resolve():
        parser.error("public-out must differ from the private answer file")
    families = GROUPS.get(args.families, args.families.split(","))
    if not families or any(f not in FAMILIES for f in families) or len(set(families)) != len(families):
        parser.error(f"families must be distinct names from {list(FAMILIES)}")
    levels = LEVELS if args.difficulty == "all" else [args.difficulty]
    selection = json.loads(args.selection.read_text()) if args.selection else {}
    questions = []
    # Interleave families: --limit gives a varied smoke sample, not one family.
    for level in levels:
        for i in range(args.count):
            for family in families:
                seeds = selection.get(family, {}).get(level, list(range(args.seed, args.seed + args.count)))
                if len(seeds) != args.count or len(set(seeds)) != len(seeds):
                    parser.error(f"selection for {family}/{level} must contain count distinct seeds")
                questions.append(build_question(family, seeds[i], level, args.split))
    ids = [q["id"] for q in questions]
    if len(ids) != len(set(ids)):
        raise ValueError("generated duplicate instances; choose different seeds")
    data = {"version": VERSION, "scoring": "json", "calibration": "unmeasured",
            "description": "Procedural challenge set; hard/extreme are structural settings, not measured model difficulty.",
            "questions": questions}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    if args.public_out:
        args.public_out.parent.mkdir(parents=True, exist_ok=True)
        args.public_out.write_text("\n".join(json.dumps(public_question(q), ensure_ascii=False) for q in questions) + "\n")
    print(f"Generated {len(questions)} questions in {args.out}; model difficulty is unmeasured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
