import json
import random
from pathlib import Path

VERBS_PATH = Path(__file__).parent / "data" / "verbs.json"
CONJUGATIONS_PATH = Path(__file__).parent / "data" / "conjugations.json"
PERSON_LABELS = ["eu", "tu", "el/ea", "noi", "voi", "ei/ele"]
MASTERY_COUNT = 10  # must get all MASTERY_COUNT recent answers correct to be mastered


def load_verbs() -> list[dict]:
    with open(VERBS_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_conjugations() -> dict[str, list[str]]:
    """Present-tense forms per verb, built by scripts/build_conjugations.py."""
    if not CONJUGATIONS_PATH.exists():
        return {}
    with open(CONJUGATIONS_PATH, encoding="utf-8") as f:
        return json.load(f)


def present_line(forms: list[str] | None) -> str:
    """One line of present tense for the answer card, or "" if unknown."""
    if not forms or len(forms) != len(PERSON_LABELS):
        return ""
    return "Prezent: " + " · ".join(f"{p} {f}" for p, f in zip(PERSON_LABELS, forms))


def is_mastered(history: list[bool]) -> bool:
    return len(history) >= MASTERY_COUNT and all(history[-MASTERY_COUNT:])


def word_weight(history: list[bool]) -> float:
    if is_mastered(history):
        return 0.05  # show rarely for spaced review
    if not history:
        return 1.0
    recent = history[-MASTERY_COUNT:]
    correct_count = sum(recent)
    return max(0.1, (MASTERY_COUNT - correct_count) / MASTERY_COUNT)


def select_word(
    verbs: list[dict],
    stats: dict[tuple[str, str], list[bool]],
    direction: str,
) -> dict:
    weights = [word_weight(stats.get((v["ro"], direction), [])) for v in verbs]
    (chosen,) = random.choices(verbs, weights=weights, k=1)
    return chosen


def build_card(word: dict, verbs: list[dict], direction: str) -> dict:
    """
    Returns a dict with:
        question:      str
        correct_answer: str
        choices:       list[str]  (3 items, shuffled)
        correct_idx:   int        (index of correct answer in choices)
    """
    if direction == "ro_en":
        question = f"What does *{word['ro']}* mean?"
        correct_answer = word["en"]
        pool = [v["en"] for v in verbs if v["ro"] != word["ro"]]
    else:
        question = f"How do you say *{word['en']}* in Romanian?"
        correct_answer = word["ro"]
        pool = [v["ro"] for v in verbs if v["ro"] != word["ro"]]

    # Deduplicate pool entries identical to the correct answer; different verbs
    # can share a gloss, which would otherwise show two identical buttons.
    pool = list(dict.fromkeys(opt for opt in pool if opt != correct_answer))
    distractors = random.sample(pool, k=min(2, len(pool)))

    choices = [correct_answer] + distractors
    random.shuffle(choices)
    correct_idx = choices.index(correct_answer)

    return {
        "question": question,
        "correct_answer": correct_answer,
        "choices": choices,
        "correct_idx": correct_idx,
    }
