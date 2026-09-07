"""Shortest guarded XOR programs, including mandatory actions and exact path counts."""

from collections import deque

from puzzles.common import answer_instruction, table


def transition(state, action):
    bits, visited = state
    if bits & action["on"] != action["on"] or bits & action["off"]:
        return None
    return bits ^ action["flip"], visited | action["visit"]


def traverse(instance):
    start = (instance["start"], 0)
    goal = (instance["goal"], instance["required"]) if instance.get("goal") is not None else None
    actions = sorted(instance["actions"], key=lambda a: a["id"])
    queue = deque([start])
    distances, ways, parent = {start: 0}, {start: 1}, {}
    while queue:
        state = queue.popleft()
        distance = distances[state]
        if goal in distances and distance >= distances[goal]:
            break
        for action in actions:
            nxt = transition(state, action)
            if nxt is None:
                continue
            if nxt not in distances:
                distances[nxt] = distance + 1
                ways[nxt] = ways[state]
                parent[nxt] = (state, action["id"])
                queue.append(nxt)
            elif distances[nxt] == distance + 1:
                ways[nxt] += ways[state]
    return distances, ways, parent


def search(instance):
    start = (instance["start"], 0)
    goal = (instance["goal"], instance["required"])
    distances, ways, parent = traverse(instance)
    if goal not in distances:
        return None, len(distances)
    plan, states = [], [goal[0]]
    cursor = goal
    while cursor != start:
        cursor, name = parent[cursor]
        plan.append(name)
        states.append(cursor[0])
    return {"moves": plan[::-1], "states": states[::-1], "shortest_count": ways[goal]}, len(distances)


def solve(instance):
    answer, _ = search(instance)
    if answer is None:
        raise ValueError("switchboard has no solution")
    return answer


def generate(rng, level):
    n, action_count, min_length = (10, 9, 9) if level == "hard" else (13, 12, 13)
    for _ in range(150):
        actions = []
        for i in range(action_count):
            flip = sum(1 << bit for bit in rng.sample(range(n), rng.randint(2, 4)))
            guard = rng.choice(range(n))
            on = (1 << guard) if rng.randrange(2) else 0
            off = (1 << guard) if not on else 0
            actions.append({"id": f"A{i:02}", "on": on, "off": off, "flip": flip,
                            "visit": (1 << i) if i < 3 else 0})
        instance = {"bits": n, "start": rng.randrange(1 << n),
                    "required": 7, "actions": actions}
        distances, _, _ = traverse(instance)
        candidates = [(state, depth) for state, depth in distances.items()
                      if state[1] == 7 and depth >= min_length]
        if candidates and len(distances) >= 200:
            farthest = max(depth for _, depth in candidates)
            instance["goal"] = rng.choice(sorted(state[0] for state, depth in candidates if depth >= farthest - 1))
            return instance
    raise ValueError("could not generate a sufficiently deep reachable switchboard")


def render(instance):
    return (
        "The Switchboard Vault\nThere are " + str(instance["bits"]) + " binary switches. "
        "A state is an integer bitmask: bit 0 is the least significant bit. Each action "
        "takes one move. It is legal iff (state AND on)=on and (state AND off)=0. "
        "A legal action replaces state with state XOR flip. Guards are checked BEFORE "
        "flipping; actions may be repeated. In addition, A00, A01 and A02 must EACH "
        "have been executed at least once before finishing. No other restrictions apply.\n"
        f"Start state: {instance['start']}. Required final state: {instance['goal']}.\n\n"
        + table(["Action", "on", "off", "flip"],
                [[a[k] for k in ("id", "on", "off", "flip")] for a in instance["actions"]])
        + "\nFind a plan with the fewest moves. Among shortest plans choose the "
        "lexicographically smallest sequence of action IDs. Also give its state sequence "
        "including the initial state, and the number of ALL distinct shortest action "
        "sequences satisfying both requirements. Lexicographic order compares the "
        "first differing ID as a string."
        + answer_instruction('{"moves": ["A00", "..."], "states": [initial, ...], "shortest_count": 1}')
    )
