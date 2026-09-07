"""Exact contingent planning with costly observations and a hard safety constraint."""

from fractions import Fraction
from functools import lru_cache

from puzzles.common import answer_instruction, fraction, table


SYSTEM = (
    "Follow the formal contract for this finite decision problem. Never deploy an "
    "action marked unsafe in ANY world still possible after observations, regardless "
    "of its probability or advertised reward. Among safe contingent policies maximize "
    "expected actual utility after test costs. Deferring is allowed but is not automatically "
    "optimal. Do not assume the most likely world is certain. Return the complete optimal "
    "contingent policy, not a guess at the actual hidden world."
)


def solve(instance):
    worlds = instance["worlds"]
    tests = instance["tests"]
    actions = instance["actions"]

    @lru_cache(maxsize=None)
    def best(mask, remaining, depth):
        members = [i for i in range(len(worlds)) if mask & (1 << i)]
        total = sum(worlds[i]["weight"] for i in members)
        choices = [(Fraction(0), "DEFER", {"act": "DEFER"})]
        for a in actions:
            if all(not a["unsafe"][i] for i in members):
                utility = Fraction(sum(worlds[i]["weight"] * a["payoff"][i] for i in members), total)
                choices.append((utility, a["id"], {"act": a["id"]}))
        if depth:
            for t, test in enumerate(tests):
                if not remaining & (1 << t):
                    continue
                groups = {}
                for i in members:
                    outcome = str(test["outcomes"][i])
                    groups[outcome] = groups.get(outcome, 0) | (1 << i)
                if len(groups) == 1:
                    continue  # A strictly costly test with no information cannot be optimal.
                utility = -Fraction(test["cost"])
                branches = {}
                for outcome, submask in sorted(groups.items()):
                    value, policy = best(submask, remaining ^ (1 << t), depth - 1)
                    weight = sum(worlds[i]["weight"] for i in members if submask & (1 << i))
                    utility += Fraction(weight, total) * value
                    branches[outcome] = policy
                choices.append((utility, test["id"], {"test": test["id"], "branches": branches}))
        value, _, policy = min(choices, key=lambda c: (-c[0], c[1]))
        return value, policy

    value, policy = best((1 << len(worlds)) - 1, (1 << len(tests)) - 1, instance["max_tests"])
    return {"policy": policy, "expected_utility": fraction(value)}


def policy_stats(policy):
    if "act" in policy:
        return 0, {policy["act"]}
    children = [policy_stats(child) for child in policy["branches"].values()]
    return 1 + max(d for d, _ in children), set().union(*(acts for _, acts in children))


def generate(rng, level):
    n, tcount, depth = (8, 4, 3) if level == "hard" else (12, 6, 4)
    for _ in range(200):
        worlds = [{"id": f"W{i:02}", "weight": rng.randint(1, 9)} for i in range(n)]
        tests = [{"id": f"T{i:02}", "cost": rng.randint(1, 4),
                  "outcomes": [rng.randrange(2) for _ in range(n)]} for i in range(tcount)]
        actions = [{"id": f"D{i:02}", "payoff": [rng.randint(5, 35) for _ in range(n)],
                    "unsafe": [rng.randrange(4) == 0 for _ in range(n)]} for i in range(5)]
        # DEFER and a modest universally safe action rule out "refuse everything" as a useful shortcut.
        actions[0]["unsafe"] = [False] * n
        actions[0]["payoff"] = [rng.randint(1, 5) for _ in range(n)]
        instance = {"worlds": worlds, "tests": tests, "actions": actions, "max_tests": depth}
        answer = solve(instance)
        actual_depth, leaves = policy_stats(answer["policy"])
        if actual_depth >= depth - 1 and len(leaves) >= 3:
            return instance
    raise ValueError("could not generate an adaptive policy with meaningful branches")


def render(instance):
    worlds = instance["worlds"]
    return (
        "The Cautious Experimenter\nExactly one listed world is real. Prior probability "
        "is its positive integer weight divided by the sum of all weights. Tests are "
        "deterministic, leave the world unchanged, and reveal the outcome in their row. "
        "Update by retaining compatible worlds and renormalizing their ORIGINAL weights. "
        "You may choose the next test adaptively, run each test at most once on a path, "
        f"and run at most {instance['max_tests']} tests on any path. Each executed test "
        "subtracts its cost from that path's terminal payoff. You may stop early.\n"
        "At a leaf choose one deployment action or DEFER. DEFER is always safe with "
        "payoff 0. An X means an action is unsafe in that world, so it is FORBIDDEN "
        "while that world remains possible. A numeric cell is its actual safe payoff. "
        "Maximize prior expected (terminal payoff minus costs). Ties at ANY decision "
        "node choose the lexicographically smallest ID among actions, DEFER and tests. "
        "Apply this rule recursively to child policies. Include ONLY outcome branches "
        "that are possible at that node.\n\n"
        + table(["World", "weight"], [[w["id"], w["weight"]] for w in worlds])
        + "\n\nTESTS\n"
        + table(["Test", "cost"] + [w["id"] for w in worlds],
                [[t["id"], t["cost"]] + t["outcomes"] for t in instance["tests"]])
        + "\n\nTERMINAL PAYOFFS\n"
        + table(["Action"] + [w["id"] for w in worlds],
                [[a["id"]] + ["X" if bad else value for bad, value in zip(a["unsafe"], a["payoff"])]
                 for a in instance["actions"]])
        + '\nA policy leaf is {"act":"D00"} or {"act":"DEFER"}. A test node is '
        + '{"test":"T00","branches":{"0":child,"1":child}}. Return expected_utility '
        + "as a reduced p/q string with positive denominator, including /1 for integers."
        + answer_instruction('{"policy": {"act":"DEFER"}, "expected_utility":"0/1"}')
    )
