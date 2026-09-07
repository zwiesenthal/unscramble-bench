"""Independent constraint-propagation baseline for the Council of Mirrors.

Search-node count is a reproducible structural proxy, NOT a model difficulty score.
The reference solver instead enumerates all complete assignments.
"""


def council_search(instance):
    n = instance["n"]
    constraints = []
    degree = [0] * n
    for i, s in enumerate(instance["statements"]):
        refs = [j for j in range(n) if s["mask"] & (1 << j)]
        constraints.append((i, refs, s["modulus"], s["residue"], s["negate"]))
        for j in [i] + refs:
            degree[j] += 1
    nodes = 0
    solutions = []

    def propagate(domains):
        changed = True
        while changed:
            changed = False
            for i, refs, modulus, residue, negate in constraints:
                for variable in [i] + refs:
                    supported = set()
                    for candidate in domains[variable]:
                        truth_domain = {candidate} if variable == i else domains[i]
                        minimum = maximum = 0
                        for ref in refs:
                            values = {candidate} if ref == variable else domains[ref]
                            minimum += min(values)
                            maximum += max(values)
                        if any(int((total % modulus == residue) != negate) in truth_domain
                               for total in range(minimum, maximum + 1)):
                            supported.add(candidate)
                    if not supported:
                        return False
                    if supported != domains[variable]:
                        domains[variable] = supported
                        changed = True
        return True

    def visit(domains):
        nonlocal nodes
        nodes += 1
        if not propagate(domains):
            return
        unknown = [i for i, d in enumerate(domains) if len(d) == 2]
        if not unknown:
            solutions.append(sum(next(iter(d)) << i for i, d in enumerate(domains)))
            return
        variable = min(unknown, key=lambda i: (-degree[i], i))
        for value in (0, 1):
            child = [set(d) for d in domains]
            child[variable] = {value}
            visit(child)

    visit([{0, 1} for _ in range(n)])
    return sorted(solutions), nodes
