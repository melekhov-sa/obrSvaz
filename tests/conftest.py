import aiosqlite
import pytest

from bot.db.database import init_db


@pytest.fixture
async def conn():
    connection = await aiosqlite.connect(":memory:")
    connection.row_factory = aiosqlite.Row
    await init_db(connection)
    yield connection
    await connection.close()
