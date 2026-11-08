import asyncio
from datetime import date, timedelta

import db

DAY1 = date(2026, 4, 1)


def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "stats.db")
    asyncio.run(db.init_db())
    asyncio.run(db.touch_user(1, "Test User", "tester"))


def session_on(day: date):
    return asyncio.run(db.finish_session(1, day))


def test_first_session_awards_base_points(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    assert session_on(DAY1) == (10, 1)


def test_second_session_same_day_does_not_extend_streak(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    session_on(DAY1)
    award, streak = session_on(DAY1)
    assert (award, streak) == (10, 1)
    assert asyncio.run(db.get_user(1))["points"] == 20


def test_three_days_in_a_row_doubles_points(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    session_on(DAY1)
    session_on(DAY1 + timedelta(days=1))
    assert session_on(DAY1 + timedelta(days=2)) == (20, 3)


def test_gap_resets_streak(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    session_on(DAY1)
    session_on(DAY1 + timedelta(days=1))
    assert session_on(DAY1 + timedelta(days=5)) == (10, 1)


def test_level_is_remembered(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    asyncio.run(db.set_level(1, 150))
    assert asyncio.run(db.get_user(1))["level"] == 150


def test_reset_clears_points_and_streak_but_keeps_level(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    session_on(DAY1)
    asyncio.run(db.set_level(1, 150))
    asyncio.run(db.reset_stats(1))
    user = asyncio.run(db.get_user(1))
    assert (user["points"], user["streak"], user["level"]) == (0, 0, 150)
