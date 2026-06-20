"""Reminders & Timers — SQLite-backed, persistent across restarts."""

import aiosqlite
import datetime
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
        for i, r in enumerate(rows, 1):
            due = f" due {r['due_at']}" if r['due_at'] else ""
            parts.append(f"{i}. {r['text']}{due}")
        return "Your reminders: " + ". ".join(parts) + "."


async def delete_reminder(reminder_id: int = None, text_search: str = None) -> str:
    """Delete a reminder by ID or by text search."""
    await _ensure_table()
    async with aiosqlite.connect(DB) as db:
        if reminder_id is not None:
            cursor = await db.execute("SELECT text FROM reminders WHERE id = ?", (reminder_id,))
            row = await cursor.fetchone()
            if not row:
                return f"No reminder found with ID {reminder_id}, Sir."
            await db.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
            await db.commit()
            return f"Removed reminder: '{row[0]}', Sir."
        elif text_search:
            cursor = await db.execute(
                "SELECT id, text FROM reminders WHERE done = 0 AND LOWER(text) LIKE LOWER(?) LIMIT 1",
                (f"%{text_search}%",)
            )
            row = await cursor.fetchone()
            if not row:
                return f"No active reminder matching '{text_search}' found, Sir."
            await db.execute("DELETE FROM reminders WHERE id = ?", (row[0],))
            await db.commit()
            return f"Removed reminder: '{row[1]}', Sir."
        else:
            return "Please specify which reminder to delete, Sir."


async def clear_all_reminders() -> str:
    """Delete ALL reminders (both done and not done)."""
    await _ensure_table()
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM reminders")
        count = (await cursor.fetchone())[0]
        if count == 0:
            return "No reminders to clear, Sir."
        await db.execute("DELETE FROM reminders")
        await db.commit()
    return f"Cleared all {count} reminders, Sir."


async def mark_done(reminder_id: int = None, text_search: str = None) -> str:
    """Mark a reminder as done."""
    await _ensure_table()
    async with aiosqlite.connect(DB) as db:
        if reminder_id is not None:
            await db.execute("UPDATE reminders SET done = 1 WHERE id = ?", (reminder_id,))
        elif text_search:
            await db.execute(
                "UPDATE reminders SET done = 1 WHERE done = 0 AND LOWER(text) LIKE LOWER(?)",
                (f"%{text_search}%",)
            )
        await db.commit()
    return "Marked as done, Sir."


_broadcasted_reminders = set()

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
        
        # Filter out any that were already broadcasted in this runtime
        result = []
        for r in rows:
            if r["id"] not in _broadcasted_reminders:
                result.append({"id": r["id"], "text": r["text"], "due_at": r["due_at"]})
                _broadcasted_reminders.add(r["id"])
                
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
