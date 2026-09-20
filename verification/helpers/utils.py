"""Small helper functions used across the cog."""

import random

from .constants import DEFAULT_TEXT_CHALLENGES


def normalize_emoji(e) -> str:
    """Normalize an emoji string for comparison (strips variation selector)."""
    if e is None:
        return ""
    s = str(e).strip()
    if s.startswith("<") and s.endswith(">"):
        return s
    return s.replace("\ufe0f", "")


def generate_challenge(text_challenges=None) -> tuple[str, str, bool]:
    """
    Returns (prompt, correct_answer_as_string, is_math).
    Randomly picks between a math problem and a text prompt.
    """
    if random.random() < 0.5:
        op = random.choice(["+", "-", "*"])
        if op == "+":
            a, b = random.randint(1, 20), random.randint(1, 20)
            answer = a + b
        elif op == "-":
            a, b = random.randint(1, 20), random.randint(1, 20)
            if a < b:
                a, b = b, a
            answer = a - b
        else:
            a, b = random.randint(1, 10), random.randint(1, 10)
            answer = a * b
        return (f"What is {a} {op} {b}?", str(answer), True)

    pool = text_challenges or [(p, a) for p, a in DEFAULT_TEXT_CHALLENGES]
    prompt, answer = random.choice(pool)
    return (prompt, answer, False)