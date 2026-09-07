#!/usr/bin/env python3
"""Mine unique councils that resist a specified constraint-propagation baseline.

This searches new candidates for the requested wall-clock budget. It does not run
or claim to approximate any language model. Every candidate is checked by both an
exhaustive reference solver and an independent propagation/backtracking solver.
Checkpoints contain the best cases plus enough seeds to reproduce them exactly.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from puzzles import liars
from puzzles.common import VERSION, canonical, rng_for
from puzzles.diagnostics import council_search


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=60)
    parser.add_argument("--start-seed", type=int, default=10000)
    parser.add_argument("--keep", type=int, default=8, help="best cases per difficulty")
    parser.add_argument("--out", type=Path, default=Path("runs/mining/councils.json"))
    args = parser.parse_args(argv)
    if args.seconds <= 0 or args.keep < 1 or args.start_seed < 0:
        parser.error("seconds and keep must be positive; start-seed must be nonnegative")
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.monotonic()
    pools = {"hard": [], "extreme": []}
    checked = {"hard": 0, "extreme": 0}
    rejected = []
    seed = args.start_seed
    last_log = started
    args.out.parent.mkdir(parents=True, exist_ok=True)

    def checkpoint(complete=False):
        report = {"version": VERSION, "started_at": started_at,
                  "finished_at": datetime.now(timezone.utc).isoformat() if complete else None,
                  "elapsed_seconds": round(time.monotonic() - started, 3),
                  "requested_seconds": args.seconds, "complete": complete,
                  "next_seed": seed, "candidates_checked": checked, "rejected": rejected,
                  "method": "unique exhaustive solution; highest independent propagation search nodes",
                  "model_evaluations": 0, "selected": pools}
        temporary = args.out.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, indent=2) + "\n")
        temporary.replace(args.out)

    while time.monotonic() - started < args.seconds:
        for level in ("hard", "extreme"):
            try:
                instance = liars.generate(rng_for("liars", seed, level, "dev"), level)
            except ValueError as exc:
                rejected.append({"seed": seed, "level": level, "reason": str(exc)})
                continue
            reference = liars.solutions(instance, limit=2)
            independent, nodes = council_search(instance)
            if reference != independent or len(reference) != 1:
                raise AssertionError(f"independent solver disagreement at seed {seed}: {reference} vs {independent}")
            checked[level] += 1
            row = {"seed": seed, "difficulty": level, "split": "dev", "search_nodes": nodes,
                   "instance_hash": hashlib.sha256(canonical(instance).encode()).hexdigest(),
                   "instance": instance, "answer": liars.solve(instance)}
            pool = pools[level]
            pool.append(row)
            pool.sort(key=lambda r: (-r["search_nodes"], r["seed"]))
            del pool[args.keep:]
        seed += 1
        if time.monotonic() - last_log >= 30:
            checkpoint()
            print(json.dumps({"elapsed": round(time.monotonic() - started), "checked": checked,
                              "best_nodes": {k: v[0]["search_nodes"] if v else None for k, v in pools.items()}}), flush=True)
            last_log = time.monotonic()
    checkpoint(complete=True)
    print(f"Saved {args.out}; checked {sum(checked.values())} unique candidates", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
