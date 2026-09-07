#!/usr/bin/env python3
"""Sample candidates, reject generation failures, rank by transparent structural proxies.

Selection is NOT calibrated LLM difficulty. Council mining has its own timed search.
Writes seed selections usable with generate_hard_questions.py and an audit report.
"""

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from puzzles import contracts, policy, residues, switchboard
from puzzles.common import LEVELS, VERSION
from puzzles.suite import FAMILIES, build_question


def subset_answer(instance, selected):
    jobs = instance["jobs"]
    mask = sum(1 << i for i, j in enumerate(jobs) if j["id"] in selected)
    chosen = [j for j in jobs if j["id"] in selected]
    cost = sum(j["cost"] for j in chosen)
    harm = [sum(j["harm"][i] for j in chosen) for i in range(len(instance["caps"]))]
    valid = (cost <= instance["budget"] and all(x <= y for x, y in zip(harm, instance["caps"]))
             and all(j["authorized"] and j["keeps_stop"] and mask & j["requires"] == j["requires"]
                     and not mask & j["conflicts"] for j in chosen))
    return valid, {"selected": sorted(selected), "benefit": sum(j["benefit"] for j in chosen), "cost": cost, "harm": harm}


def greedy_contract(instance):
    selected = []
    for job in sorted(instance["jobs"], key=lambda j: (-Fraction(j["benefit"], j["cost"]), j["id"])):
        valid, _ = subset_answer(instance, selected + [job["id"]])
        if valid:
            selected.append(job["id"])
    return subset_answer(instance, selected)[1]


def metrics(question):
    f, p, a = question["family"], question["instance"], question["answer"]
    if f == "contracts":
        greedy = greedy_contract(p)
        proxy = contracts.optimize(p, proxy=True)[0]
        proxy_safe = subset_answer(p, proxy["selected"])[0]
        return {"greedy_regret": a["benefit"] - greedy["benefit"], "proxy_violates_contract": int(not proxy_safe),
                "prefixes_explored": contracts.optimize(p)[1]}
    if f == "switchboard":
        return {"shortest_moves": len(a["moves"]), "reachable_states": switchboard.search(p)[1],
                "shortest_solutions": a["shortest_count"]}
    if f == "residues":
        return {"near_miss_secrets": len(residues.candidates({**p, "corrupt": p["corrupt"] + 1})),
                "secret_digits": len(str(a["secret"]))}
    if f == "policy":
        depth, actions = policy.policy_stats(a["policy"])
        return {"adaptive_depth": depth, "distinct_terminal_actions": len(actions),
                "utility_denominator": Fraction(a["expected_utility"]).denominator}
    if f == "causal":
        return {"counterfactual_denominator": Fraction(a["counterfactual"]).denominator,
                "compatible_worlds": a["compatible_worlds"],
                "distinct_probabilities": len({a[k] for k in ("observational", "interventional", "counterfactual")})}
    if f == "relay":
        return {"shortest_moves": len(a["moves"]),
                "counterfactual_denominator": Fraction(a["counterfactual"]).denominator,
                "shortest_solutions": a["shortest_count"]}
    if f == "anagram":
        return {"nonlinear_steps": sum(not x.startswith(("add ", "multiply ")) for x in a["instructions"]),
                "distinct_values": len(set(a["values"])), "total_value_digits": sum(len(str(x)) for x in a["values"])}
    if f == "ledger":
        return {"rejected_rows": len(p["events"]) - len(a["accepted"]), "successful_uses": len(a["uses"]),
                "exhausted_tokens": sum(x == 0 for x in a["remaining"].values())}
    if f == "noninterference":
        return {"latest_first_leak_public": max(w["public"] for w in a["witnesses"].values()),
                "largest_first_leak_secret": max(w["secret_b"] for w in a["witnesses"].values()),
                "safe_programs": len(a["safe"])}
    raise ValueError(f"no selection metric for {f}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=int, default=100, help="per family per difficulty")
    parser.add_argument("--seed", type=int, default=100)
    parser.add_argument("--keep", type=int, default=4)
    parser.add_argument("--families", default=",".join(f for f in FAMILIES if f != "liars"))
    parser.add_argument("--out", type=Path, default=Path("runs/mining/selection.json"))
    args = parser.parse_args(argv)
    if not 0 < args.keep <= args.candidates or args.seed < 0:
        parser.error("need 0 < keep <= candidates and a nonnegative seed")
    families = args.families.split(",")
    if len(set(families)) != len(families) or any(f not in FAMILIES or f == "liars" for f in families):
        parser.error("choose distinct registered families except liars; use mine_council.py for liars")
    started = time.monotonic()
    started_at = datetime.now(timezone.utc).isoformat()
    selection, stats, failures = {}, {}, []
    for family in families:
        selection[family], stats[family] = {}, {}
        for level in LEVELS:
            candidates = []
            for seed in range(args.seed, args.seed + args.candidates):
                try:
                    question = build_question(family, seed, level)
                    values = metrics(question)
                except ValueError as exc:
                    failures.append({"family": family, "difficulty": level, "seed": seed, "error": str(exc)})
                    continue
                candidates.append({"seed": seed, "metrics": values, "instance_hash": question["instance_hash"]})
            # Dict insertion order defines the documented primary/secondary criteria.
            candidates.sort(key=lambda row: (tuple(-v for v in row["metrics"].values()), row["seed"]))
            if len(candidates) < args.keep:
                raise ValueError(f"not enough valid candidates for {family}/{level}")
            chosen = candidates[:args.keep]
            selection[family][level] = [r["seed"] for r in chosen]
            stats[family][level] = {"successful_candidates": len(candidates), "selected": chosen}
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(selection, indent=2) + "\n")
            print(f"{family}/{level}: {len(candidates)} candidates; best={chosen[0]['metrics']}", flush=True)
    report = {"version": VERSION, "started_at": started_at, "finished_at": datetime.now(timezone.utc).isoformat(),
              "elapsed_seconds": round(time.monotonic() - started, 3), "requested_candidates": args.candidates,
              "model_evaluations": 0, "calibration": "structural proxies only", "families": stats,
              "generation_failures": failures}
    report_path = args.out.with_name(args.out.stem + "-report.json")
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Saved {args.out} and {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
