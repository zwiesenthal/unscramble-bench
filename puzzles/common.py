"""Formatting and deterministic seeds; no model calls or solver dependencies."""

import hashlib
import json
import random
from fractions import Fraction


VERSION = "hard-v1"
LEVELS = ("hard", "extreme")
SPLITS = ("dev", "validation", "test")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def rng_for(family, seed, level, split):
    material = canonical([VERSION, family, seed, level, split]).encode()
    return random.Random(int.from_bytes(hashlib.sha256(material).digest(), "big"))


def fraction(value):
    value = Fraction(value)
    return f"{value.numerator}/{value.denominator}"


def table(headers, rows):
    def row(values):
        return "| " + " | ".join(map(str, values)) + " |"
    return "\n".join([row(headers), row(["---"] * len(headers))] + [row(r) for r in rows]) + "\n"


def answer_instruction(shape):
    return (
        '\n\nReturn only JSON with exactly one outer key "answer". Its value must have '
        f"this shape: {shape}. Use JSON integers for integer fields, not strings or "
        "decimals. Array order matters; object key order does not."
    )
