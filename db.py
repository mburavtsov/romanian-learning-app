import json
from datetime import date, timedelta

import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "stats.db"
DEFAULT_LEVEL = 50
POINTS_PER_SESSION = 10
STREAK_BONUS_FROM = 3  # points double from this many consecutive days


async def init_db() -> None:
    DB_PATH.parent.mkdir(exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS word_stats (
                user_id   INTEGER NOT NULL,
                word_ro   TEXT    NOT NULL,
                direction TEXT    NOT NULL,
                history   TEXT    NOT NULL DEFAULT '[]',
                PRIMARY KEY (user_id, word_ro, direction)
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id    INTEGER PRIMARY KEY,
                first_seen TEXT    NOT NULL,
                last_seen  TEXT    NOT NULL,
                name       TEXT,
                username   TEXT,
                level      INTEGER NOT NULL DEFAULT 50,
                points     INTEGER NOT NULL DEFAULT 0,
                streak     INTEGER NOT NULL DEFAULT 0,
                last_day   TEXT
            )
            """
        )
        await db.commit()


async def touch_user(user_id: int, name: str, username: str | None) -> None:
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, first_seen, last_seen, name, username)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                last_seen = excluded.last_seen,
                name      = excluded.name,
                username  = excluded.username
            """,
            (user_id, today, today, name, username),
        )
        await db.commit()


async def get_user(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE user_id=?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
    if row is None:
        return {"level": DEFAULT_LEVEL, "points": 0, "streak": 0, "last_day": None}
    return dict(row)


async def set_level(user_id: int, level: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET level=? WHERE user_id=?", (level, user_id))
        await db.commit()


async def finish_session(user_id: int, today: date) -> tuple[int, int]:
    """Award points for a finished session. Returns (points_awarded, streak_days)."""
    user = await get_user(user_id)
    last_day = user["last_day"]
    streak = user["streak"]

    if last_day == today.isoformat():
        pass  # already counted today, second session does not extend the streak
    elif last_day == (today - timedelta(days=1)).isoformat():
        streak += 1
    else:
        streak = 1

    award = POINTS_PER_SESSION * (2 if streak >= STREAK_BONUS_FROM else 1)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET points=points+?, streak=?, last_day=? WHERE user_id=?",
            (award, streak, today.isoformat(), user_id),
        )
        await db.commit()
    return award, streak


async def get_history(user_id: int, word_ro: str, direction: str) -> list[bool]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT history FROM word_stats WHERE user_id=? AND word_ro=? AND direction=?",
            (user_id, word_ro, direction),
        ) as cursor:
            row = await cursor.fetchone()
    if row is None:
        return []
    return json.loads(row[0])


async def record_answer(
    user_id: int, word_ro: str, direction: str, correct: bool
) -> None:
    history = await get_history(user_id, word_ro, direction)
    history.append(correct)
    history = history[-10:]  # keep last 10
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO word_stats (user_id, word_ro, direction, history)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, word_ro, direction)
            DO UPDATE SET history = excluded.history
            """,
            (user_id, word_ro, direction, json.dumps(history)),
        )
        await db.commit()


async def get_all_stats(user_id: int) -> list[tuple[str, str, list[bool]]]:
    """Return all (word_ro, direction, history) rows for a user."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT word_ro, direction, history FROM word_stats WHERE user_id=?",
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
    return [(r[0], r[1], json.loads(r[2])) for r in rows]


async def reset_stats(user_id: int) -> None:
    """Delete all word history, points and streak for a user. Keeps the level."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM word_stats WHERE user_id=?", (user_id,))
        await db.execute(
            "UPDATE users SET points=0, streak=0, last_day=NULL WHERE user_id=?",
            (user_id,),
        )
        await db.commit()
