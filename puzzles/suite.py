"""A registry of plain modules, a JSON question builder, and reference verification."""

import hashlib

from puzzles import anagram, causal, contracts, ledger, liars, noninterference, policy, relay, residues, switchboard
from puzzles.common import LEVELS, SPLITS, VERSION, canonical, rng_for


FAMILIES = {
    "anagram": anagram,
    "residues": residues,
    "liars": liars,
    "switchboard": switchboard,
    "causal": causal,
    "relay": relay,
    "contracts": contracts,
    "policy": policy,
    "ledger": ledger,
    "noninterference": noninterference,
}
GROUPS = {"puzzles": list(FAMILIES)[:6], "alignment": list(FAMILIES)[6:], "all": list(FAMILIES)}


def build_question(family, seed, difficulty="hard", split="dev"):
    if family not in FAMILIES or difficulty not in LEVELS or split not in SPLITS:
        raise ValueError("unknown family, difficulty, or split")
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    module = FAMILIES[family]
    instance = module.generate(rng_for(family, seed, difficulty, split), difficulty)
    digest = hashlib.sha256(canonical(instance).encode()).hexdigest()
    question = {
        "id": f"{family}-{difficulty}-{digest[:16]}", "version": VERSION,
        "family": family, "difficulty": difficulty, "split": split, "seed": seed,
        "scoring": "json", "instance_hash": digest, "instance": instance,
        "prompt": module.render(instance), "answer": module.solve(instance),
    }
    if hasattr(module, "SYSTEM"):
        question["system_prompt"] = module.SYSTEM
    return question


def verify_question(question, regenerate=False):
    from main import exact_json_equal

    module = FAMILIES[question["family"]]
    instance = question["instance"]
    if question["version"] != VERSION or question["scoring"] != "json":
        raise ValueError(f"{question['id']}: unsupported version or scoring")
    if question["difficulty"] not in LEVELS or question["split"] not in SPLITS:
        raise ValueError("unknown difficulty or split")
    if type(question["seed"]) is not int or question["seed"] < 0:
        raise ValueError("seed must be a nonnegative integer")
    digest = hashlib.sha256(canonical(instance).encode()).hexdigest()
    if digest != question["instance_hash"]:
        raise ValueError(f"{question['id']}: instance hash mismatch")
    if question["id"] != f"{question['family']}-{question['difficulty']}-{digest[:16]}":
        raise ValueError("question id does not match content")
    if question["prompt"] != module.render(instance):
        raise ValueError(f"{question['id']}: prompt does not match the instance")
    if question.get("system_prompt") != getattr(module, "SYSTEM", None):
        raise ValueError(f"{question['id']}: authoritative rules changed")
    if not exact_json_equal(question["answer"], module.solve(instance)):
        raise ValueError(f"{question['id']}: answer disagrees with reference solver")
    if regenerate:
        fresh = module.generate(rng_for(question["family"], question["seed"], question["difficulty"], question["split"]),
                                question["difficulty"])
        if canonical(fresh) != canonical(instance):
            raise ValueError(f"{question['id']}: generation is not reproducible from its metadata")
    return True


def public_question(question):
    """Explicit allowlist; no answers, seeds, reference instances or solutions."""
    return {key: question[key] for key in ("id", "family", "difficulty", "prompt", "system_prompt") if key in question}
