"""Exact observation / intervention / counterfactual probabilities in binary SCMs."""

from fractions import Fraction

from puzzles.common import answer_instruction, fraction, table


def evaluate(instance, world, intervention=None):
    values = {f"U{i}": (world >> i) & 1 for i in range(instance["latent"])}
    intervention = intervention or {}
    for node in instance["nodes"]:
        if node["id"] in intervention:
            values[node["id"]] = intervention[node["id"]]
            continue
        xs = [values[name] for name in node["inputs"]]
        op = node["op"]
        if op == "xor":
            value = sum(xs) % 2
        elif op == "and":
            value = int(all(xs))
        elif op == "or":
            value = int(any(xs))
        elif op == "majority":
            value = int(sum(xs) >= 2)
        else:
            raise ValueError(f"unknown gate: {op}")
        values[node["id"]] = value ^ node["invert"]
    return values


def solve(instance):
    evidence = instance["evidence"]
    action, value = next(iter(instance["intervention"].items()))
    target = instance["target"]
    compatible = observed_n = observed_y = do_y = cf_y = 0
    total = 1 << instance["latent"]
    for world in range(total):
        factual = evaluate(instance, world)
        changed = evaluate(instance, world, instance["intervention"])
        do_y += changed[target]
        if all(factual[k] == v for k, v in evidence.items()):
            compatible += 1
            cf_y += changed[target]
            if factual[action] == value:
                observed_n += 1
                observed_y += factual[target]
    if not compatible or not observed_n:
        raise ValueError("conditioning event has probability zero")
    return {"compatible_worlds": compatible,
            "observational": fraction(Fraction(observed_y, observed_n)),
            "interventional": fraction(Fraction(do_y, total)),
            "counterfactual": fraction(Fraction(cf_y, compatible))}


def generate(rng, level):
    latent, count = (7, 13) if level == "hard" else (10, 21)
    for _ in range(200):
        available = [f"U{i}" for i in range(latent)]
        nodes = []
        for i in range(count):
            inputs = rng.sample(available, 3)
            # Keep a causal spine instead of mostly unrelated gates.
            if i and rng.random() < .75 and f"V{i - 1}" not in inputs:
                inputs[0] = f"V{i - 1}"
            nodes.append({"id": f"V{i}", "op": rng.choice(["xor", "and", "or", "majority"]),
                          "inputs": inputs, "invert": rng.randrange(2)})
            available.append(f"V{i}")
        instance = {"latent": latent, "nodes": nodes, "target": f"V{count - 1}"}
        factual = evaluate(instance, rng.randrange(1 << latent))
        action = f"V{rng.randrange(2, count - 3)}"
        evidence_names = rng.sample([f"V{i}" for i in range(count - 1) if f"V{i}" != action], 3)
        instance["evidence"] = {name: factual[name] for name in evidence_names}
        instance["intervention"] = {action: rng.randrange(2)}
        try:
            answer = solve(instance)
        except ValueError:
            continue
        probabilities = [answer[k] for k in ("observational", "interventional", "counterfactual")]
        if (answer["compatible_worlds"] >= 6 and len(set(probabilities)) == 3
                and all(p not in ("0/1", "1/1") for p in probabilities)):
            if any(evaluate(instance, world)[instance["target"]] !=
                   evaluate(instance, world, instance["intervention"])[instance["target"]]
                   for world in range(1 << latent)):
                return instance
    raise ValueError("could not generate an informative causal contrast")


def render(instance):
    action, value = next(iter(instance["intervention"].items()))
    evidence = " and ".join(f"{k}={v}" for k, v in instance["evidence"].items())
    y = instance["target"]
    return (
        "The Counterfactual Relay\nThis is a fully specified structural causal model, "
        f"not an inference from correlations. U0..U{instance['latent'] - 1} are mutually "
        "independent fair bits. All 2^" + str(instance["latent"]) + " exogenous assignments "
        "are equally likely. Evaluate nodes in table order. xor is parity of the three "
        "inputs, and/or are Boolean, majority is 1 iff at least two inputs are 1. "
        "After applying the gate, XOR its output with invert.\n\n"
        + table(["Node", "gate", "inputs", "invert"],
                [[n["id"], n["op"], ",".join(n["inputs"]), n["invert"]] for n in instance["nodes"]])
        + f"\n\nFactual evidence E: {evidence}. Intervention: replace the equation for {action} "
        + f"with the constant {value}, leaving every other equation unchanged. Target: {y}.\n"
        + "Compute these FOUR quantities:\n"
        + "1. compatible_worlds: number of exogenous assignments satisfying E in the original model.\n"
        + f"2. observational: P({y}=1 | E AND {action}={value}) in the original model.\n"
        + f"3. interventional: P({y}=1 | do({action}={value})) over ALL exogenous assignments, WITHOUT conditioning on E.\n"
        + f"4. counterfactual: P({y}_do=1 | E factual): first retain only exogenous assignments satisfying "
        + "E in the original model, then reuse those SAME assignments in the intervened model. "
        + "Do NOT re-filter using the intervened evidence values.\n"
        + "Return fractions as reduced strings p/q with positive denominator, including /1 for integers."
        + answer_instruction('{"compatible_worlds": 4, "observational": "1/2", "interventional": "1/3", "counterfactual": "2/3"}')
    )
