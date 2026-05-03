"""Reminders & Timers — SQLite-backed, persistent across restarts."""

import aiosqlite
import datetime
import asyncio
from config import settings

DB = settings.DB_PATH


async def _ensure_table():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                due_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                done INTEGER DEFAULT 0
            )
        """)
        await db.commit()


async def add_reminder(text: str, due_at: str = None) -> str:
    """Add a reminder. due_at is ISO format or None for instant notes."""
    await _ensure_table()
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT INTO reminders (text, due_at) VALUES (?, ?)",
            (text, due_at)
        )
        await db.commit()
    if due_at:
        return f"Reminder set: '{text}' for {due_at}, Sir."
    return f"Noted, Sir. I'll remember: '{text}'."


async def get_reminders(include_done: bool = False) -> str:
    await _ensure_table()
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        if include_done:
            cursor = await db.execute("SELECT * FROM reminders ORDER BY created_at DESC LIMIT 10")
        else:
            cursor = await db.execute("SELECT * FROM reminders WHERE done = 0 ORDER BY due_at ASC LIMIT 10")
        rows = await cursor.fetchall()
        if not rows:
            return "No active reminders, Sir. You're all clear."
        parts = []
        for r in rows:
            due = f" (due {r['due_at']})" if r['due_at'] else ""
            parts.append(f"{r['text']}{due}")
        return "Your reminders: " + ". ".join(parts) + "."


async def get_due_reminders() -> list[dict]:
    """Return reminders that are due now (for the scheduler)."""
    await _ensure_table()
    now = datetime.datetime.now().isoformat()
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM reminders WHERE done = 0 AND due_at IS NOT NULL AND due_at <= ?",
            (now,)
        )
        rows = await cursor.fetchall()
        result = [{"id": r["id"], "text": r["text"], "due_at": r["due_at"]} for r in rows]
        if result:
            ids = [r["id"] for r in result]
            placeholders = ",".join("?" * len(ids))
            await db.execute(f"UPDATE reminders SET done = 1 WHERE id IN ({placeholders})", ids)
            await db.commit()
        return result


async def clear_done() -> str:
    await _ensure_table()
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM reminders WHERE done = 1")
        await db.commit()
    return "Cleared completed reminders, Sir."
