from datetime import datetime, timezone

import aiosqlite


async def upsert_user(conn: aiosqlite.Connection, telegram_id: int, username: str | None, first_name: str | None) -> None:
    await conn.execute(
        """
        INSERT INTO users (telegram_id, username, first_name)
        VALUES (?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET username = excluded.username, first_name = excluded.first_name
        """,
        (telegram_id, username, first_name),
    )
    await conn.commit()


async def get_user(conn: aiosqlite.Connection, telegram_id: int) -> aiosqlite.Row | None:
    cursor = await conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    return await cursor.fetchone()


async def link_user(conn: aiosqlite.Connection, telegram_id: int, marzban_login: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    await conn.execute(
        "UPDATE users SET marzban_login = NULL, linked_at = NULL WHERE marzban_login = ? AND telegram_id != ?",
        (marzban_login, telegram_id),
    )
    await conn.execute(
        "UPDATE users SET marzban_login = ?, linked_at = ? WHERE telegram_id = ?",
        (marzban_login, now, telegram_id),
    )
    await conn.commit()


async def get_all_users(conn: aiosqlite.Connection) -> list[aiosqlite.Row]:
    cursor = await conn.execute("SELECT * FROM users")
    return await cursor.fetchall()


async def get_linked_users(conn: aiosqlite.Connection) -> list[aiosqlite.Row]:
    cursor = await conn.execute("SELECT * FROM users WHERE marzban_login IS NOT NULL")
    return await cursor.fetchall()


async def unlink_by_login(conn: aiosqlite.Connection, marzban_login: str) -> aiosqlite.Row | None:
    cursor = await conn.execute("SELECT * FROM users WHERE marzban_login = ?", (marzban_login,))
    row = await cursor.fetchone()
    if row is None:
        return None
    await conn.execute(
        "UPDATE users SET marzban_login = NULL, linked_at = NULL WHERE marzban_login = ?",
        (marzban_login,),
    )
    await conn.commit()
    return row
