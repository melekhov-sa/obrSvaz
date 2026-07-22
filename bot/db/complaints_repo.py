from datetime import datetime, timezone

import aiosqlite


async def add_complaint(conn: aiosqlite.Connection, telegram_id: int, text: str) -> int:
    now = datetime.now(timezone.utc).isoformat()
    cursor = await conn.execute(
        "INSERT INTO complaints (telegram_id, text, created_at) VALUES (?, ?, ?)",
        (telegram_id, text, now),
    )
    await conn.commit()
    return cursor.lastrowid


async def count_all(conn: aiosqlite.Connection) -> int:
    cursor = await conn.execute("SELECT COUNT(*) FROM complaints")
    row = await cursor.fetchone()
    return row[0]


async def count_since(conn: aiosqlite.Connection, since_iso: str) -> int:
    cursor = await conn.execute("SELECT COUNT(*) FROM complaints WHERE created_at >= ?", (since_iso,))
    row = await cursor.fetchone()
    return row[0]


async def count_by_user(conn: aiosqlite.Connection) -> list[aiosqlite.Row]:
    cursor = await conn.execute(
        "SELECT telegram_id, COUNT(*) as cnt FROM complaints GROUP BY telegram_id ORDER BY cnt DESC"
    )
    return await cursor.fetchall()


async def count_by_day(conn: aiosqlite.Connection, since_iso: str) -> list[aiosqlite.Row]:
    cursor = await conn.execute(
        """
        SELECT substr(created_at, 1, 10) as day, COUNT(*) as cnt
        FROM complaints
        WHERE created_at >= ?
        GROUP BY day
        ORDER BY day
        """,
        (since_iso,),
    )
    return await cursor.fetchall()
