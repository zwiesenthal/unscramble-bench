"""Recover a program in a finite grammar, then execute its dependent arithmetic."""

from collections import defaultdict
from math import comb, gcd

from puzzles.common import answer_instruction, table


TENS = ["", "", "twenty", "thirty", "forty"]
SMALL = ("zero one two three four five six seven eight nine ten eleven twelve "
         "thirteen fourteen fifteen sixteen seventeen eighteen nineteen").split()
TEMPLATES = {
    "add": "add {n}",
    "multiply": "multiply by {n}",
    "power": "raise to the power {n}",
    "fibonacci": "take fibonacci of the remainder modulo {n}",
    "binomial": "choose three from the remainder modulo {n}",
    "totient": "take the totient then add {n}",
    "divisors": "sum the positive divisors then add {n}",
    "reverse": "reverse the decimal digits then add {n}",
}


def words(n):
    return SMALL[n] if n < 20 else TENS[n // 10] + (" " + SMALL[n % 10] if n % 10 else "")


def signature(text):
    return "".join(sorted(c for c in text.lower() if c != " "))


def grammar():
    candidates = defaultdict(list)
    for op, template in TEMPLATES.items():
        for n in range(2, 50):
            phrase = template.format(n=words(n))
            candidates[signature(phrase)].append((op, n, phrase))
    return candidates


GRAMMAR = grammar()


def apply(op, x, n, modulus):
    if op == "add":
        return (x + n) % modulus
    if op == "multiply":
        return (x * n) % modulus
    if op == "power":
        return pow(x, n, modulus)
    if op == "fibonacci":
        a, b = 0, 1
        for _ in range(x % n):
            a, b = b, a + b
        return a % modulus
    if op == "binomial":
        return comb(x % n, 3) % modulus if x % n >= 3 else 0
    if op == "totient":
        return (sum(gcd(k, x) == 1 for k in range(1, x + 1)) + n) % modulus
    if op == "divisors":
        return (sum(k for k in range(1, x + 1) if x % k == 0) + n) % modulus
    if op == "reverse":
        return (int(str(x)[::-1]) + n) % modulus
    raise ValueError(f"unknown operation: {op}")


def solve(instance):
    x = instance["start"]
    phrases, values = [], []
    for scrambled in instance["lines"]:
        candidates = GRAMMAR.get(signature(scrambled), [])
        if len(candidates) != 1:
            raise ValueError("instruction is not unique in the stated grammar")
        op, n, phrase = candidates[0]
        x = apply(op, x, n, instance["modulus"])
        phrases.append(phrase)
        values.append(x)
    return {"instructions": phrases, "values": values}


def generate(rng, level):
    count = 10 if level == "hard" else 16
    for _ in range(100):
        ops = list(TEMPLATES)
        rng.shuffle(ops)
        ops += rng.choices(list(TEMPLATES), k=count - len(ops))
        lines = []
        for op in ops:
            n = rng.randint(2, 49)
            phrase = TEMPLATES[op].format(n=words(n))
            if len(GRAMMAR[signature(phrase)]) != 1:
                break
            letters = list(phrase.replace(" ", ""))
            rng.shuffle(letters)
            # Grouping deliberately does not preserve word boundaries.
            lines.append(" ".join("".join(letters[i:i + 7]) for i in range(0, len(letters), 7)))
        if len(lines) != count:
            continue
        instance = {"start": rng.randint(100, 999), "modulus": 1009, "lines": lines}
        result = solve(instance)
        # Avoid chains collapsing to repeated small constants.
        if len(set(result["values"])) >= count - 2 and 0 not in result["values"]:
            return instance
    raise ValueError("could not generate a nondegenerate anagram circuit")


def render(instance):
    rules = [
        [TEMPLATES["add"], "x + N"],
        [TEMPLATES["multiply"], "x * N"],
        [TEMPLATES["power"], "x ** N"],
        [TEMPLATES["fibonacci"], "F(x mod N), F(0)=0, F(1)=1"],
        [TEMPLATES["binomial"], "C(x mod N,3); 0 when x mod N < 3"],
        [TEMPLATES["totient"], "phi(x) + N; phi(0)=0, phi(1)=1"],
        [TEMPLATES["divisors"], "sum of positive divisors of x, plus N; sum at x=0 is 0"],
        [TEMPLATES["reverse"], "reverse decimal digits of x, discard leading zeroes, then add N"],
    ]
    return (
        "The Anagram Engine\nRecover and execute a program. Each numbered line is "
        "an independent anagram of exactly one instruction in the finite grammar below. "
        "Ignore spaces in the scrambled line; use every letter exactly once. {n} is "
        "replaced with the standard lowercase English spelling of an integer from 2 "
        "through 49 (spaces, no hyphens, e.g. 'twenty three'). There are no other words "
        "or instructions. Each line has exactly one match in this grammar.\n\n"
        + table(["Instruction template", "Meaning (N is the decoded integer)"], rules)
        + f"\n\nStart with x={instance['start']}. After EVERY instruction reduce x modulo "
        + f"{instance['modulus']} to its least nonnegative residue. Each next instruction "
        + "uses that reduced x. phi counts 1<=k<=x coprime to x.\n\n"
        + table(["Line", "Scrambled instruction"], enumerate(instance["lines"], 1))
        + answer_instruction('{"instructions": ["decoded line 1", "..."], "values": [x_after_line_1, ...]}')
    )
