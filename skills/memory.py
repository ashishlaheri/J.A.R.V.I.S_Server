"""Persistent memory — 'Remember that...' / 'What is my...' system."""

import aiosqlite
from config import settings

DB = settings.DB_PATH


async def _ensure_table():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


async def remember(key: str, value: str) -> str:
    await _ensure_table()
    async with aiosqlite.connect(DB) as db:
        # Upsert — update if key exists
        existing = await db.execute("SELECT id FROM memory WHERE LOWER(key) = LOWER(?)", (key,))
        row = await existing.fetchone()
        if row:
            await db.execute("UPDATE memory SET value = ? WHERE id = ?", (value, row[0]))
        else:
            await db.execute("INSERT INTO memory (key, value) VALUES (?, ?)", (key, value))
        await db.commit()
    return f"Got it, Sir. I'll remember that."


async def recall(key: str) -> str:
    await _ensure_table()
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute(
            "SELECT value FROM memory WHERE LOWER(key) LIKE LOWER(?)",
            (f"%{key}%",)
        )
        row = await cursor.fetchone()
        if row:
            return row[0]
        return None


async def forget(key: str) -> str:
    await _ensure_table()
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM memory WHERE LOWER(key) LIKE LOWER(?)", (f"%{key}%",))
        await db.commit()
    return f"Forgotten, Sir."


async def get_all_memories() -> str:
    await _ensure_table()
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute("SELECT key, value FROM memory ORDER BY created_at DESC LIMIT 20")
        rows = await cursor.fetchall()
        if not rows:
            return "I don't have anything stored in memory yet, Sir."
        parts = [f"{k}: {v}" for k, v in rows]
        return "Here's what I remember: " + ". ".join(parts) + "."
