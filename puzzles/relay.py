"""A three-stage puzzle: repair a ledger, unlock a plan, then answer a counterfactual."""

import copy

from puzzles import causal, residues, switchboard
from puzzles.common import answer_instruction


def unlocked_board(instance, secret):
    board = copy.deepcopy(instance["board"])
    mask = (1 << board["bits"]) - 1
    board["start"] = board.pop("encoded_start") ^ (secret & mask)
    board["goal"] = board.pop("encoded_goal") ^ ((secret // (1 << board["bits"])) & mask)
    return board


def solve(instance):
    first = residues.solve(instance["ledger"])
    second = switchboard.solve(unlocked_board(instance, first["secret"]))
    third = copy.deepcopy(instance["causal"])
    third["intervention"] = {instance["intervention_node"]: len(second["moves"]) % 2}
    final = causal.solve(third)
    return {"secret": first["secret"], "corrupt_rows": first["corrupt_rows"],
            "moves": second["moves"], "shortest_count": second["shortest_count"],
            "counterfactual": final["counterfactual"]}


def generate(rng, level):
    ledger = residues.generate(rng, level)
    secret = residues.solve(ledger)["secret"]
    board = switchboard.generate(rng, level)
    parity = len(switchboard.solve(board)["moves"]) % 2
    model = causal.generate(rng, level)
    # Keep the causal generator's nondegeneracy checks valid at the unlocked parity.
    for _ in range(100):
        if next(iter(model["intervention"].values())) == parity:
            break
        model = causal.generate(rng, level)
    else:
        raise ValueError("could not match the relay intervention parity")
    intervention_node = next(iter(model.pop("intervention")))
    mask = (1 << board["bits"]) - 1
    board["encoded_start"] = board.pop("start") ^ (secret & mask)
    board["encoded_goal"] = board.pop("goal") ^ ((secret // (1 << board["bits"])) & mask)
    return {"ledger": ledger, "board": board, "causal": model, "intervention_node": intervention_node}


def render(instance):
    def task_only(text):
        return text.split('\nReturn only JSON with exactly one outer key "answer".')[0]

    board = {**instance["board"], "start": "DECODED_START", "goal": "DECODED_GOAL"}
    model = {**instance["causal"], "intervention": {instance["intervention_node"]: "PARITY"}}
    return (
        "The Three-Lock Relay\nSolve three dependent stages. Earlier answers determine "
        "later inputs. Submit ONLY the final combined answer specified at the end. "
        "Local stage descriptions define their mathematical rules; intermediate fields "
        "not requested in the combined answer need not be submitted.\n\nSTAGE 1\n"
        + task_only(residues.render(instance["ledger"]))
        + "\n\nSTAGE 2: use the recovered secret x. Let B=2^" + str(board["bits"])
        + f". DECODED_START = {board['encoded_start']} XOR (x mod B). "
        + f"DECODED_GOAL = {board['encoded_goal']} XOR (floor(x/B) mod B). "
        + "All XORs are bitwise.\n" + task_only(switchboard.render(board))
        + "\n\nSTAGE 3: let PARITY be the number of moves in the shortest valid stage-2 "
        + "plan, modulo 2. Use it as the intervention's constant (0 or 1).\n"
        + task_only(causal.render(model))
        + "\n\nCOMBINED ANSWER: stage-1 secret and corrupt row IDs, stage-2 canonical "
        + "shortest move sequence and total shortest-sequence count, and stage-3 "
        + "counterfactual probability as a reduced fraction."
        + answer_instruction('{"secret":123,"corrupt_rows":["R00"],"moves":["A00", "..."],"shortest_count":1,"counterfactual":"1/2"}')
    )
