import asyncio

import db
import quiz


def test_fresh_word_is_likely_but_unknown_history_is():
    assert quiz.word_weight([]) == 1.0
    assert quiz.word_weight([False] * 10) > 0.05


def test_mastered_word_is_rare():
    assert quiz.is_mastered([True] * 10)
    assert quiz.word_weight([True] * 10) == 0.05


def test_card_choices_are_unique_even_when_verbs_share_a_gloss():
    verbs = [
        {"ro": "a fi", "en": "to be"},
        {"ro": "a exista", "en": "to be"},  # same gloss as "a fi"
        {"ro": "a face", "en": "to do"},
        {"ro": "a merge", "en": "to go"},
    ]
    for _ in range(50):
        card = quiz.build_card(verbs[0], verbs, "ro_en")
        assert len(set(card["choices"])) == len(card["choices"])
        assert card["choices"][card["correct_idx"]] == "to be"


def test_record_answer_keeps_only_the_last_ten(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "stats.db")
    asyncio.run(db.init_db())
    for correct in [True] * 9 + [False, True]:
        asyncio.run(db.record_answer(1, "a fi", "ro_en", correct))
    assert asyncio.run(db.get_history(1, "a fi", "ro_en")) == [True] * 8 + [False, True]


def test_present_line_has_all_six_forms():
    line = quiz.present_line(["fac", "faci", "face", "facem", "faceți", "fac"])
    assert line.startswith("Prezent: eu fac")
    assert line.count("·") == 5


def test_present_line_is_empty_without_data():
    assert quiz.present_line(None) == ""
    assert quiz.present_line(["fac"]) == ""
