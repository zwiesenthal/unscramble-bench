"""Unique fixed points of mutually referential, modular truth statements."""

from puzzles.common import answer_instruction, table


def truth_of(mask, statement):
    count = (mask & statement["mask"]).bit_count()
    value = count % statement["modulus"] == statement["residue"]
    return value != statement["negate"]


def solutions(instance, limit=None):
    found = []
    for mask in range(1 << instance["n"]):
        if all(bool(mask & (1 << i)) == truth_of(mask, s) for i, s in enumerate(instance["statements"])):
            found.append(mask)
            if limit is not None and len(found) >= limit:
                break
    return found


def solve(instance):
    found = solutions(instance, limit=2)
    if len(found) != 1:
        raise ValueError(f"expected one truth assignment, got {len(found)} (capped at 2)")
    return {"true": [i + 1 for i in range(instance["n"]) if found[0] & (1 << i)]}


def generate(rng, level):
    n = 14 if level == "hard" else 18
    for _ in range(100):
        planted = rng.randrange(1 << n)
        if not n // 3 <= planted.bit_count() <= 2 * n // 3:
            continue
        statements = []
        for i in range(n):
            refs = rng.sample([j for j in range(n) if j != i], rng.randint(3, 6))
            mask = sum(1 << j for j in refs)
            modulus = rng.choice([2, 3])
            residue = rng.randrange(modulus)
            test = (planted & mask).bit_count() % modulus == residue
            statements.append({"mask": mask, "modulus": modulus, "residue": residue,
                               "negate": test != bool(planted & (1 << i))})
        instance = {"n": n, "statements": statements}
        if solutions(instance, limit=2) == [planted]:
            return instance
    raise ValueError("could not generate a unique truth assignment")


def render(instance):
    rows = []
    for i, s in enumerate(instance["statements"], 1):
        refs = ", ".join(f"S{j + 1}" for j in range(instance["n"]) if s["mask"] & (1 << j))
        relation = "is NOT" if s["negate"] else "is"
        rows.append([f"S{i}", f"Among {{{refs}}}, the count of true statements modulo {s['modulus']} {relation} {s['residue']}."])
    return (
        "The Council of Mirrors\nEvery statement below is either true or false. "
        "Its truth value must agree with the claim it makes about the OTHER statements. "
        "A false statement means its entire claim is false. Modulo uses the least "
        "nonnegative remainder; NOT negates only the equality. There is exactly one "
        "consistent assignment. Return the numbers of all true statements in increasing "
        "order (S1 is 1).\n\n"
        + table(["Statement", "Claim"], rows)
        + answer_instruction('{"true": [1, 4, ...]}')
    )
