import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    marzban_login TEXT,
    linked_at TEXT
);

CREATE TABLE IF NOT EXISTS complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
);

CREATE TABLE IF NOT EXISTS reminders_sent (
    telegram_id INTEGER NOT NULL,
    sent_for_date TEXT NOT NULL,
    PRIMARY KEY (telegram_id, sent_for_date)
);

CREATE TABLE IF NOT EXISTS link_tokens (
    token TEXT PRIMARY KEY,
    marzban_login TEXT NOT NULL,
    created_at TEXT NOT NULL,
    used_at TEXT,
    used_by INTEGER
);
"""


async def init_db(conn: aiosqlite.Connection) -> None:
    await conn.executescript(SCHEMA)
    await conn.commit()


async def open_db(path: str) -> aiosqlite.Connection:
    conn = await aiosqlite.connect(path)
    conn.row_factory = aiosqlite.Row
    await init_db(conn)
    return conn
