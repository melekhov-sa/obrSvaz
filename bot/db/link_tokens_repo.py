import secrets
import string
from datetime import datetime, timezone

import aiosqlite


def generate_token() -> str:
    alphabet = string.ascii_uppercase + string.digits
    suffix = "".join(secrets.choice(alphabet) for _ in range(8))
    return f"LNK_{suffix}"


async def create_token(conn: aiosqlite.Connection, marzban_login: str) -> str:
    token = generate_token()
    now = datetime.now(timezone.utc).isoformat()
    await conn.execute(
        "INSERT INTO link_tokens (token, marzban_login, created_at) VALUES (?, ?, ?)",
        (token, marzban_login, now),
    )
    await conn.commit()
    return token


async def get_token(conn: aiosqlite.Connection, token: str) -> aiosqlite.Row | None:
    cursor = await conn.execute("SELECT * FROM link_tokens WHERE token = ?", (token,))
    return await cursor.fetchone()


async def mark_used(conn: aiosqlite.Connection, token: str, telegram_id: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
    await conn.execute(
        "UPDATE link_tokens SET used_at = ?, used_by = ? WHERE token = ?",
        (now, telegram_id, token),
    )
    await conn.commit()
