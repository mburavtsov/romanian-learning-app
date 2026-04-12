import json
import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "stats.db"


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
        await db.commit()


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
    """Delete all word history for a user."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM word_stats WHERE user_id=?", (user_id,))
        await db.commit()
