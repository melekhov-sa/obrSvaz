import aiosqlite


async def was_sent(conn: aiosqlite.Connection, telegram_id: int, sent_for_date: str) -> bool:
    cursor = await conn.execute(
        "SELECT 1 FROM reminders_sent WHERE telegram_id = ? AND sent_for_date = ?",
        (telegram_id, sent_for_date),
    )
    row = await cursor.fetchone()
    return row is not None


async def mark_sent(conn: aiosqlite.Connection, telegram_id: int, sent_for_date: str) -> None:
    await conn.execute(
        "INSERT OR IGNORE INTO reminders_sent (telegram_id, sent_for_date) VALUES (?, ?)",
        (telegram_id, sent_for_date),
    )
    await conn.commit()
