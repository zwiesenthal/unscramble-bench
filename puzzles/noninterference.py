"""Finite semantic information-flow checks, including permitted declassification."""

from puzzles.common import answer_instruction, table


SYSTEM = (
    "Audit each finite program against the stated information-release contract. "
    "A secret-dependent intermediate value is not automatically a leak; judge the "
    "actual observable output over the entire finite domain. Conversely, a rare "
    "output change still violates the contract. Only the two low secret bits may "
    "be released. Return exact counterexamples for every unsafe program and approve "
    "every safe program; rejecting all programs does not satisfy the task."
)


def execute(program, public, secret, width):
    mask = (1 << width) - 1
    values = {"public": public, "secret": secret}
    for instruction in program["code"]:
        xs = [values[a] if isinstance(a, str) else a for a in instruction["args"]]
        op = instruction["op"]
        if op == "xor":
            value = xs[0] ^ xs[1]
        elif op == "and":
            value = xs[0] & xs[1]
        elif op == "add":
            value = xs[0] + xs[1]
        elif op == "sub":
            value = xs[0] - xs[1]
        elif op == "mul":
            value = xs[0] * xs[1]
        elif op == "shr":
            value = xs[0] >> xs[1]
        elif op == "eq":
            value = int(xs[0] == xs[1])
        elif op == "mux":
            value = xs[1] if xs[0] != 0 else xs[2]
        else:
            raise ValueError(f"unknown operation: {op}")
        values[instruction["dst"]] = value & mask
    return values


def run(program, public, secret, width):
    return execute(program, public, secret, width)[program["output"]]


def witness(instance, program):
    for public in range(instance["public_bound"]):
        outputs = [run(program, public, secret, instance["width"])
                   for secret in range(1 << instance["width"])]
        for a, first in enumerate(outputs):
            for b in range(a + 4, len(outputs), 4):
                if outputs[b] != first:
                    return {"public": public, "secret_a": a, "secret_b": b,
                            "output_a": first, "output_b": outputs[b]}
    return None


def solve(instance):
    safe, witnesses = [], {}
    for program in sorted(instance["programs"], key=lambda p: p["id"]):
        counterexample = witness(instance, program)
        if counterexample is None:
            safe.append(program["id"])
        else:
            witnesses[program["id"]] = counterexample
    return {"safe": safe, "witnesses": witnesses}


def make_program(rng, width, safe, public_bound):
    code = []

    def emit(op, *args):
        name = f"r{len(code)}"
        code.append({"dst": name, "op": op, "args": list(args)})
        return name

    modulus = 1 << width
    planted_secret = rng.randrange(modulus)
    planted_public = rng.randrange(public_bound)
    # All candidates have the same control-flow shape. Some safe programs have
    # an unreachable branch; others branch on permitted information only.
    low_only = safe and rng.random() < .2
    predicates = []
    for _ in range(3):
        a, b, c = rng.randrange(1, modulus, 2), rng.randrange(1, modulus), rng.randrange(modulus)
        bitmask = 3 if low_only else sum(1 << bit for bit in rng.sample(range(width), 3 if width == 6 else 5))
        x = emit("mul", "secret", a)
        y = emit("mul", "public", b)
        x = emit("add", x, y)
        x = emit("xor", x, c)
        x = emit("and", x, bitmask)
        target = (((planted_secret * a + planted_public * b) % modulus) ^ c) & bitmask
        if safe and not low_only:
            target = rng.randrange(modulus) & bitmask
        predicates.append(emit("eq", x, target))
    condition = emit("and", predicates[0], predicates[1])
    condition = emit("and", condition, predicates[2])
    low = emit("and", "secret", 3)
    other = emit("xor", low, 4)
    x = emit("mux", condition, other, low)
    x = emit("add", x, "public")
    x = emit("xor", x, rng.randrange(modulus))
    return {"code": code, "output": x}, predicates, low_only


def generate(rng, level):
    width, public_bound = (6, 8) if level == "hard" else (8, 16)
    count = 6 if level == "hard" else 10
    safe_count = rng.randint(2, 4) if level == "hard" else rng.randint(3, 6)
    desired = [True] * safe_count + [False] * (count - safe_count)
    rng.shuffle(desired)
    domain = {"width": width, "public_bound": public_bound}
    programs = []
    for i, safe in enumerate(desired):
        for _ in range(200):
            program, predicates, low_only = make_program(rng, width, safe, public_bound)
            if (witness(domain, program) is None) != safe:
                continue
            if safe and not low_only:
                # Avoid an obviously impossible single condition: every PAIR of
                # conditions must hold together somewhere, despite the full audit
                # finding no prohibited release. This is checked, not assumed.
                supported = set()
                for public in range(public_bound):
                    for secret in range(1 << width):
                        values = execute(program, public, secret, width)
                        for pair in [(0, 1), (0, 2), (1, 2)]:
                            if all(values[predicates[j]] for j in pair):
                                supported.add(pair)
                    if len(supported) == 3:
                        break
                if len(supported) != 3:
                    continue
            programs.append({"id": f"P{i:02}", **program})
            break
        else:
            raise ValueError("could not generate a semantically classified information-flow program")
    return {"width": width, "public_bound": public_bound, "programs": programs}


def render(instance):
    blocks = []
    for program in instance["programs"]:
        code = [[i["dst"], i["op"] + "(" + ",".join(map(str, i["args"])) + ")"] for i in program["code"]]
        blocks.append(program["id"] + "\n" + table(["Register", "Expression"], code)
                      + "\nReturn " + program["output"])
    return (
        "The Information-Flow Audit\nPrograms operate on unsigned " + str(instance["width"])
        + f"-bit integers. public ranges from 0 through {instance['public_bound'] - 1}, and "
        + f"secret from 0 through {(1 << instance['width']) - 1}, independently. After EACH "
        + f"instruction reduce its result modulo {1 << instance['width']}. All registers "
        + "are fresh assignments. xor/and are bitwise, shr(a,b) is logical right shift, "
        + "eq(a,b) is 1 iff equal else 0, mux(c,a,b) selects a iff c!=0 else b. add/sub/mul "
        + "are integer arithmetic before the per-instruction reduction. Only the single "
        + "returned integer is observable; intermediate values, runtime and source code "
        + "are not observations in this toy contract.\n"
        + "The contract permits revealing secret mod 4 and nothing else. A program is SAFE "
        + "iff for EVERY public input and EVERY pair a,b with a mod 4=b mod 4, its output "
        + "is identical for secret=a and secret=b. List safe program IDs in ascending order. "
        + "For each unsafe program return the lexicographically FIRST triple (public,a,b) "
        + "with a<b witnessing a violation, plus the two actual outputs. Search order is "
        + "public first, then a, then b, all increasing.\n\n"
        + "\n\n".join(blocks)
        + answer_instruction('{"safe":["P00", "..."], "witnesses":{"P01":{"public":0,"secret_a":0,"secret_b":4,"output_a":0,"output_b":1}}}')
    )
