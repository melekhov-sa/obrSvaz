import aiosqlite

from bot.db.database import init_db


async def test_init_db_creates_all_tables():
    conn = await aiosqlite.connect(":memory:")
    try:
        await init_db(conn)

        cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in await cursor.fetchall()}

        assert {"users", "complaints", "reminders_sent", "link_tokens"}.issubset(tables)
    finally:
        await conn.close()
