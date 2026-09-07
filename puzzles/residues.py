"""Decode an affine residue code with adversarially corrupted rows."""

from itertools import combinations
from math import gcd

from puzzles.common import answer_instruction, table


def merge(a, m, b, n):
    """Generalized CRT: x=a mod m and x=b mod n, or no solution."""
    g = gcd(m, n)
    if (b - a) % g:
        return None
    q = n // g
    k = ((b - a) // g * pow(m // g, -1, q)) % q if q > 1 else 0
    return (a + m * k) % (m * q), m * q


def candidates(instance):
    rows = instance["rows"]
    good_count = len(rows) - instance["corrupt"]
    found = set()
    for chosen in combinations(rows, good_count):
        a, m = 0, 1
        for row in chosen:
            b = ((row["r"] - row["b"]) * pow(row["a"], -1, row["m"])) % row["m"]
            merged = merge(a, m, b, row["m"])
            if merged is None:
                break
            a, m = merged
        else:
            for x in range(a, instance["bound"], m):
                mismatches = sum((r["a"] * x + r["b"]) % r["m"] != r["r"] for r in rows)
                if mismatches == instance["corrupt"]:
                    found.add(x)
    return sorted(found)


def solve(instance):
    found = candidates(instance)
    if len(found) != 1:
        raise ValueError(f"expected one residue solution, got {len(found)}")
    x = found[0]
    repaired = [(r["a"] * x + r["b"]) % r["m"] for r in instance["rows"]]
    return {
        "secret": x,
        "corrupt_rows": [r["id"] for r, value in zip(instance["rows"], repaired) if r["r"] != value],
        "repaired_residues": repaired,
    }


def generate(rng, level):
    moduli = [7, 9, 11, 13, 17, 19, 23, 25, 27, 29, 31]
    n, corrupt, bound = (9, 2, 10**7) if level == "hard" else (11, 3, 10**9)
    if level == "extreme":
        moduli = [17, 19, 23, 25, 27, 29, 31, 37, 41, 49, 51]
    for _ in range(100):
        x = rng.randrange(bound // 10, bound)
        mods = rng.sample(moduli, n)
        damaged = set(rng.sample(range(n), corrupt))
        rows = []
        for i, m in enumerate(mods):
            a = rng.choice([a for a in range(1, m) if gcd(a, m) == 1])
            b = rng.randrange(m)
            r = (a * x + b) % m
            if i in damaged:
                r = (r + rng.randrange(1, m)) % m
            rows.append({"id": f"R{i:02}", "a": a, "b": b, "m": m, "r": r})
        instance = {"bound": bound, "corrupt": corrupt, "rows": rows}
        if candidates(instance) == [x]:
            return instance
    raise ValueError("could not generate a unique residue code")


def render(instance):
    return (
        "The Damaged Observatory Ledger\nA single integer secret x satisfies "
        f"0 <= x < {instance['bound']}. Each instrument should have reported "
        "r=(a*x+b) mod m, using the least nonnegative residue. Exactly "
        f"{instance['corrupt']} rows report the WRONG r; all a, b, m entries are accurate. "
        "Corrupt rows need not be adjacent and moduli need not be coprime. There is "
        "exactly one possible x. Recover x, identify the corrupt row IDs in table "
        "order, and repair every residue, also in table order.\n\n"
        + table(["ID", "a", "b", "m", "reported r"],
                [[r[k] for k in ("id", "a", "b", "m", "r")] for r in instance["rows"]])
        + answer_instruction('{"secret": 123, "corrupt_rows": ["R00", "..."], "repaired_residues": [1, ...]}')
    )
