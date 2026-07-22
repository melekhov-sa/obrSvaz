# VPN Feedback Telegram Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Telegram bot that collects VPN outage complaints, reminds users about subscription renewal based on Marzban panel data, lets users self-check their status, and gives the admin a broadcast/stats channel.

**Architecture:** aiogram 3 bot in polling mode, SQLite for persistence (users, complaints, link tokens, reminder log), a thin Marzban REST API client, and an APScheduler daily job for renewal reminders. Deployed via Docker Compose on a separate Ubuntu server.

**Tech Stack:** Python 3.12, aiogram 3, aiosqlite, httpx, APScheduler, python-dotenv, pytest + pytest-asyncio for tests, Docker + docker-compose for deployment.

## Global Constraints

- Design source of truth: `docs/superpowers/specs/2026-07-22-vpn-feedback-bot-design.md`.
- Single admin, identified by numeric Telegram ID in `ADMIN_ID` env var.
- Polling mode only — no webhook, no public HTTP endpoint.
- Account linking is token-based (`/genlink` → deep link), no `/link @username` command.
- Renewal reminder threshold configurable via `REMINDER_DAYS` env var, default `3`.
- Unit tests cover the DB layer, the Marzban client, and the reminders job only — handler wiring is manually verified per the spec's own testing section (no automated Telegram-side tests). This is a deliberate, already-approved scope decision, not a gap.
- Deployment target: Ubuntu server via Docker Compose, code lives at `github.com/melekhov-sa/obrSvaz` on branch `main`. The agent implementing this plan does not have access to that server — the final "run it on the server" step is manual, for the user to execute themselves.
- Out of scope (per spec): config/QR issuance via bot, payments/billing, automatic outage diagnostics.

## File Structure

```
bot/
  __init__.py
  config.py                # env-based Config dataclass + loader
  db/
    __init__.py
    database.py             # schema + init_db() + open_db()
    users_repo.py           # users table CRUD
    complaints_repo.py      # complaints table CRUD
    link_tokens_repo.py     # link_tokens table CRUD + token generation
    reminders_repo.py       # reminders_sent table CRUD
  marzban/
    __init__.py
    client.py                # MarzbanClient: auth + get_user()
    status.py                # UserStatus dataclass: maps API payload, expiry math
  scheduler/
    __init__.py
    reminders.py             # check_and_send_reminders(): daily job logic
  filters.py                 # IsAdmin filter
  handlers/
    __init__.py
    start.py                 # /start incl. deep-link token consumption
    complain.py               # /complain FSM flow
    status.py                 # /status
    faq.py                    # /faq inline menu
    admin.py                  # /genlink, /broadcast, /stats (admin-only router factory)
  main.py                     # wiring: bot, dispatcher, scheduler, entrypoint
tests/
  conftest.py                 # in-memory DB connection fixture
  test_config.py
  test_database.py
  test_users_repo.py
  test_complaints_repo.py
  test_link_tokens_repo.py
  test_reminders_repo.py
  test_marzban_client.py
  test_marzban_status.py
  test_reminders_job.py
requirements.txt
requirements-dev.txt
pyproject.toml                # pytest config
.env.example
.gitignore
Dockerfile
docker-compose.yml
```

---

### Task 1: Project scaffolding & configuration loader

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `bot/__init__.py`
- Create: `bot/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `bot.config.Config` (dataclass with fields `bot_token: str`, `admin_id: int`, `marzban_url: str`, `marzban_username: str`, `marzban_password: str`, `reminder_days: int`, `db_path: str`) and `bot.config.load_config() -> Config`. All later tasks that need configuration import this.

- [ ] **Step 1: Create dependency and tooling files**

`requirements.txt`:
```
aiogram==3.15.0
aiosqlite==0.20.0
httpx==0.27.2
APScheduler==3.10.4
python-dotenv==1.0.1
```

`requirements-dev.txt`:
```
-r requirements.txt
pytest==8.3.3
pytest-asyncio==0.24.0
```

`pyproject.toml`:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["."]
```

`.gitignore`:
```
.env
__pycache__/
*.pyc
.venv/
data/
*.db
.pytest_cache/
```

`.env.example`:
```
BOT_TOKEN=
ADMIN_ID=
MARZBAN_URL=https://your-marzban-panel.example.com
MARZBAN_USERNAME=
MARZBAN_PASSWORD=
REMINDER_DAYS=3
DB_PATH=/app/data/bot.db
```

`bot/__init__.py`:
```python
```
(empty file, marks `bot` as a package)

- [ ] **Step 2: Write the failing test for config loading**

`tests/test_config.py`:
```python
import pytest

from bot.config import load_config


def test_load_config_reads_required_and_defaults(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "test-token")
    monkeypatch.setenv("ADMIN_ID", "12345")
    monkeypatch.setenv("MARZBAN_URL", "https://panel.example.com")
    monkeypatch.setenv("MARZBAN_USERNAME", "admin")
    monkeypatch.setenv("MARZBAN_PASSWORD", "secret")
    monkeypatch.delenv("REMINDER_DAYS", raising=False)
    monkeypatch.delenv("DB_PATH", raising=False)

    config = load_config()

    assert config.bot_token == "test-token"
    assert config.admin_id == 12345
    assert config.marzban_url == "https://panel.example.com"
    assert config.reminder_days == 3
    assert config.db_path == "bot.db"


def test_load_config_raises_when_required_missing(monkeypatch):
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("ADMIN_ID", raising=False)
    monkeypatch.delenv("MARZBAN_URL", raising=False)
    monkeypatch.delenv("MARZBAN_USERNAME", raising=False)
    monkeypatch.delenv("MARZBAN_PASSWORD", raising=False)

    with pytest.raises(RuntimeError):
        load_config()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pip install -r requirements-dev.txt && pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bot.config'`

- [ ] **Step 4: Implement the config loader**

`bot/config.py`:
```python
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    bot_token: str
    admin_id: int
    marzban_url: str
    marzban_username: str
    marzban_password: str
    reminder_days: int
    db_path: str


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_config() -> Config:
    return Config(
        bot_token=_require("BOT_TOKEN"),
        admin_id=int(_require("ADMIN_ID")),
        marzban_url=_require("MARZBAN_URL"),
        marzban_username=_require("MARZBAN_USERNAME"),
        marzban_password=_require("MARZBAN_PASSWORD"),
        reminder_days=int(os.getenv("REMINDER_DAYS", "3")),
        db_path=os.getenv("DB_PATH", "bot.db"),
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add requirements.txt requirements-dev.txt pyproject.toml .gitignore .env.example bot/__init__.py bot/config.py tests/test_config.py
git commit -m "feat: add project scaffolding and config loader"
```

---

### Task 2: Database schema & connection helper

**Files:**
- Create: `bot/db/__init__.py`
- Create: `bot/db/database.py`
- Create: `tests/conftest.py`
- Test: `tests/test_database.py`

**Interfaces:**
- Consumes: nothing from prior tasks.
- Produces: `bot.db.database.init_db(conn: aiosqlite.Connection) -> None` and `bot.db.database.open_db(path: str) -> aiosqlite.Connection` (returns a connection with `row_factory = aiosqlite.Row` already set and schema created). All repo tasks (3-6) and `bot/main.py` depend on this. The `conn` pytest fixture in `tests/conftest.py` is used by every subsequent test file.

- [ ] **Step 1: Write the failing test**

`tests/test_database.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_database.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bot.db'`

- [ ] **Step 3: Implement schema and connection helpers**

`bot/db/__init__.py`:
```python
```
(empty file, marks `bot.db` as a package)

`bot/db/database.py`:
```python
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
```

`tests/conftest.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_database.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add bot/db/__init__.py bot/db/database.py tests/conftest.py tests/test_database.py
git commit -m "feat: add SQLite schema and connection helper"
```

---

### Task 3: Users repository

**Files:**
- Create: `bot/db/users_repo.py`
- Test: `tests/test_users_repo.py`

**Interfaces:**
- Consumes: `conn` fixture from `tests/conftest.py` (Task 2); `aiosqlite.Connection` with `row_factory = aiosqlite.Row`.
- Produces: `upsert_user(conn, telegram_id: int, username: str | None, first_name: str | None) -> None`, `get_user(conn, telegram_id: int) -> aiosqlite.Row | None`, `link_user(conn, telegram_id: int, marzban_login: str) -> None`, `get_all_users(conn) -> list[aiosqlite.Row]`, `get_linked_users(conn) -> list[aiosqlite.Row]`. Used by `bot/handlers/start.py`, `bot/handlers/status.py`, `bot/handlers/admin.py`, `bot/scheduler/reminders.py`.

- [ ] **Step 1: Write the failing tests**

`tests/test_users_repo.py`:
```python
from bot.db import users_repo


async def test_upsert_creates_new_user(conn):
    await users_repo.upsert_user(conn, 1, "ivan", "Ivan")

    user = await users_repo.get_user(conn, 1)

    assert user["telegram_id"] == 1
    assert user["username"] == "ivan"
    assert user["marzban_login"] is None


async def test_upsert_updates_existing_user(conn):
    await users_repo.upsert_user(conn, 1, "ivan", "Ivan")
    await users_repo.upsert_user(conn, 1, "ivan_new", "Ivan")

    user = await users_repo.get_user(conn, 1)

    assert user["username"] == "ivan_new"


async def test_get_user_returns_none_when_missing(conn):
    user = await users_repo.get_user(conn, 999)
    assert user is None


async def test_link_user_sets_marzban_login(conn):
    await users_repo.upsert_user(conn, 1, "ivan", "Ivan")

    await users_repo.link_user(conn, 1, "ivan_login")

    user = await users_repo.get_user(conn, 1)
    assert user["marzban_login"] == "ivan_login"
    assert user["linked_at"] is not None


async def test_link_user_reassigns_from_previous_owner(conn):
    await users_repo.upsert_user(conn, 1, "ivan", "Ivan")
    await users_repo.upsert_user(conn, 2, "petr", "Petr")
    await users_repo.link_user(conn, 1, "shared_login")

    await users_repo.link_user(conn, 2, "shared_login")

    old_owner = await users_repo.get_user(conn, 1)
    new_owner = await users_repo.get_user(conn, 2)
    assert old_owner["marzban_login"] is None
    assert new_owner["marzban_login"] == "shared_login"


async def test_get_linked_users_returns_only_linked(conn):
    await users_repo.upsert_user(conn, 1, "ivan", "Ivan")
    await users_repo.upsert_user(conn, 2, "petr", "Petr")
    await users_repo.link_user(conn, 1, "ivan_login")

    linked = await users_repo.get_linked_users(conn)

    assert len(linked) == 1
    assert linked[0]["telegram_id"] == 1


async def test_get_all_users_returns_everyone(conn):
    await users_repo.upsert_user(conn, 1, "ivan", "Ivan")
    await users_repo.upsert_user(conn, 2, "petr", "Petr")

    all_users = await users_repo.get_all_users(conn)

    assert len(all_users) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_users_repo.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bot.db.users_repo'`

- [ ] **Step 3: Implement the repository**

`bot/db/users_repo.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_users_repo.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add bot/db/users_repo.py tests/test_users_repo.py
git commit -m "feat: add users repository"
```

---

### Task 4: Complaints repository

**Files:**
- Create: `bot/db/complaints_repo.py`
- Test: `tests/test_complaints_repo.py`

**Interfaces:**
- Consumes: `conn` fixture (Task 2); `users_repo.upsert_user` (Task 3) to seed test users.
- Produces: `add_complaint(conn, telegram_id: int, text: str) -> int` (returns new complaint id), `count_all(conn) -> int`, `count_since(conn, since_iso: str) -> int`, `count_by_user(conn) -> list[aiosqlite.Row]` (rows of `(telegram_id, cnt)`). Used by `bot/handlers/complain.py` and `bot/handlers/admin.py`.

- [ ] **Step 1: Write the failing tests**

`tests/test_complaints_repo.py`:
```python
from datetime import datetime, timedelta, timezone

from bot.db import complaints_repo, users_repo


async def test_add_complaint_returns_id(conn):
    await users_repo.upsert_user(conn, 1, "ivan", "Ivan")

    complaint_id = await complaints_repo.add_complaint(conn, 1, "Не работает интернет")

    assert complaint_id == 1


async def test_count_all(conn):
    await users_repo.upsert_user(conn, 1, "ivan", "Ivan")
    await complaints_repo.add_complaint(conn, 1, "Проблема 1")
    await complaints_repo.add_complaint(conn, 1, "Проблема 2")

    assert await complaints_repo.count_all(conn) == 2


async def test_count_since_filters_by_date(conn):
    await users_repo.upsert_user(conn, 1, "ivan", "Ivan")
    await complaints_repo.add_complaint(conn, 1, "Свежая жалоба")

    future_cutoff = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    past_cutoff = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    assert await complaints_repo.count_since(conn, past_cutoff) == 1
    assert await complaints_repo.count_since(conn, future_cutoff) == 0


async def test_count_by_user_groups_correctly(conn):
    await users_repo.upsert_user(conn, 1, "ivan", "Ivan")
    await users_repo.upsert_user(conn, 2, "petr", "Petr")
    await complaints_repo.add_complaint(conn, 1, "a")
    await complaints_repo.add_complaint(conn, 1, "b")
    await complaints_repo.add_complaint(conn, 2, "c")

    counts = await complaints_repo.count_by_user(conn)
    counts_by_id = {row[0]: row[1] for row in counts}

    assert counts_by_id[1] == 2
    assert counts_by_id[2] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_complaints_repo.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bot.db.complaints_repo'`

- [ ] **Step 3: Implement the repository**

`bot/db/complaints_repo.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_complaints_repo.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add bot/db/complaints_repo.py tests/test_complaints_repo.py
git commit -m "feat: add complaints repository"
```

---

### Task 5: Link tokens repository

**Files:**
- Create: `bot/db/link_tokens_repo.py`
- Test: `tests/test_link_tokens_repo.py`

**Interfaces:**
- Consumes: `conn` fixture (Task 2).
- Produces: `generate_token() -> str` (format `LNK_` + 8 uppercase-alnum chars), `create_token(conn, marzban_login: str) -> str`, `get_token(conn, token: str) -> aiosqlite.Row | None`, `mark_used(conn, token: str, telegram_id: int) -> None`. Used by `bot/handlers/start.py` and `bot/handlers/admin.py`.

- [ ] **Step 1: Write the failing tests**

`tests/test_link_tokens_repo.py`:
```python
from bot.db import link_tokens_repo


def test_generate_token_has_expected_format():
    token = link_tokens_repo.generate_token()

    assert token.startswith("LNK_")
    assert len(token) == len("LNK_") + 8


async def test_create_token_persists_and_is_retrievable(conn):
    token = await link_tokens_repo.create_token(conn, "ivan_login")

    row = await link_tokens_repo.get_token(conn, token)

    assert row["marzban_login"] == "ivan_login"
    assert row["used_at"] is None


async def test_get_token_returns_none_for_unknown_token(conn):
    row = await link_tokens_repo.get_token(conn, "LNK_UNKNOWN")
    assert row is None


async def test_mark_used_sets_used_fields(conn):
    token = await link_tokens_repo.create_token(conn, "ivan_login")

    await link_tokens_repo.mark_used(conn, token, telegram_id=42)

    row = await link_tokens_repo.get_token(conn, token)
    assert row["used_at"] is not None
    assert row["used_by"] == 42
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_link_tokens_repo.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bot.db.link_tokens_repo'`

- [ ] **Step 3: Implement the repository**

`bot/db/link_tokens_repo.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_link_tokens_repo.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add bot/db/link_tokens_repo.py tests/test_link_tokens_repo.py
git commit -m "feat: add link tokens repository"
```

---

### Task 6: Reminders-sent repository

**Files:**
- Create: `bot/db/reminders_repo.py`
- Test: `tests/test_reminders_repo.py`

**Interfaces:**
- Consumes: `conn` fixture (Task 2); `users_repo.upsert_user` (Task 3) to seed test users.
- Produces: `was_sent(conn, telegram_id: int, sent_for_date: str) -> bool`, `mark_sent(conn, telegram_id: int, sent_for_date: str) -> None` (idempotent — safe to call twice for the same pair). Used by `bot/scheduler/reminders.py`.

- [ ] **Step 1: Write the failing tests**

`tests/test_reminders_repo.py`:
```python
from bot.db import reminders_repo, users_repo


async def test_was_sent_false_when_not_recorded(conn):
    assert await reminders_repo.was_sent(conn, 1, "2026-08-01") is False


async def test_mark_sent_then_was_sent_true(conn):
    await users_repo.upsert_user(conn, 1, "ivan", "Ivan")

    await reminders_repo.mark_sent(conn, 1, "2026-08-01")

    assert await reminders_repo.was_sent(conn, 1, "2026-08-01") is True


async def test_mark_sent_is_idempotent(conn):
    await users_repo.upsert_user(conn, 1, "ivan", "Ivan")

    await reminders_repo.mark_sent(conn, 1, "2026-08-01")
    await reminders_repo.mark_sent(conn, 1, "2026-08-01")

    assert await reminders_repo.was_sent(conn, 1, "2026-08-01") is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_reminders_repo.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bot.db.reminders_repo'`

- [ ] **Step 3: Implement the repository**

`bot/db/reminders_repo.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_reminders_repo.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add bot/db/reminders_repo.py tests/test_reminders_repo.py
git commit -m "feat: add reminders-sent repository"
```

---

### Task 7: Marzban API client

**Files:**
- Create: `bot/marzban/__init__.py`
- Create: `bot/marzban/client.py`
- Create: `bot/marzban/status.py`
- Test: `tests/test_marzban_client.py`
- Test: `tests/test_marzban_status.py`

**Interfaces:**
- Consumes: nothing from prior tasks (standalone module).
- Produces: `MarzbanClient(base_url: str, username: str, password: str, transport: httpx.BaseTransport | None = None)` with `async get_user(login: str) -> dict | None` (returns Marzban's raw JSON payload, or `None` on 404) and `MarzbanAuthError` exception; `UserStatus` dataclass with `from_api(login: str, data: dict) -> UserStatus` and `.days_until_expiry(now_timestamp: int) -> int | None`. Used by `bot/handlers/status.py` and `bot/scheduler/reminders.py`.
- Assumption (isolated to `UserStatus.from_api`): Marzban's `GET /api/user/{login}` response includes `status`, `used_traffic`, `data_limit`, `expire` (unix timestamp or `null`) fields, matching the documented Marzban REST API. If the actual panel version differs, only this one mapping method needs adjustment.

- [ ] **Step 1: Write the failing tests for `UserStatus`**

`tests/test_marzban_status.py`:
```python
from bot.marzban.status import UserStatus


def test_from_api_maps_fields():
    status = UserStatus.from_api(
        "ivan", {"status": "active", "used_traffic": 500, "data_limit": 1000, "expire": 1000086400}
    )

    assert status.login == "ivan"
    assert status.status == "active"
    assert status.used_traffic_bytes == 500
    assert status.data_limit_bytes == 1000
    assert status.expire_timestamp == 1000086400


def test_days_until_expiry_computes_full_days():
    status = UserStatus.from_api("ivan", {"expire": 1_000_000_000 + 3 * 86400})

    assert status.days_until_expiry(now_timestamp=1_000_000_000) == 3


def test_days_until_expiry_none_when_no_expiry():
    status = UserStatus.from_api("ivan", {"expire": None})

    assert status.days_until_expiry(now_timestamp=1_000_000_000) is None


def test_days_until_expiry_negative_when_already_expired():
    status = UserStatus.from_api("ivan", {"expire": 1_000_000_000 - 86400})

    assert status.days_until_expiry(now_timestamp=1_000_000_000) < 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_marzban_status.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bot.marzban'`

- [ ] **Step 3: Implement `UserStatus`**

`bot/marzban/__init__.py`:
```python
```
(empty file, marks `bot.marzban` as a package)

`bot/marzban/status.py`:
```python
from dataclasses import dataclass


@dataclass
class UserStatus:
    login: str
    status: str
    used_traffic_bytes: int
    data_limit_bytes: int | None
    expire_timestamp: int | None

    @classmethod
    def from_api(cls, login: str, data: dict) -> "UserStatus":
        return cls(
            login=login,
            status=data.get("status", "unknown"),
            used_traffic_bytes=data.get("used_traffic", 0),
            data_limit_bytes=data.get("data_limit"),
            expire_timestamp=data.get("expire"),
        )

    def days_until_expiry(self, now_timestamp: int) -> int | None:
        if self.expire_timestamp is None:
            return None
        seconds_left = self.expire_timestamp - now_timestamp
        return seconds_left // 86400
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_marzban_status.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Write the failing tests for `MarzbanClient`**

`tests/test_marzban_client.py`:
```python
import httpx
import pytest

from bot.marzban.client import MarzbanAuthError, MarzbanClient


def _handler_factory(user_payload: dict | None, status_code: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/admin/token":
            return httpx.Response(200, json={"access_token": "test-token", "token_type": "bearer"})
        if request.url.path == "/api/user/ivan":
            if user_payload is None:
                return httpx.Response(404, json={"detail": "Not found"})
            return httpx.Response(status_code, json=user_payload)
        return httpx.Response(404)

    return handler


async def test_get_user_returns_data():
    transport = httpx.MockTransport(
        _handler_factory({"username": "ivan", "status": "active", "used_traffic": 123, "data_limit": 1000, "expire": 1999999999})
    )
    client = MarzbanClient("https://panel.example.com", "admin", "pass", transport=transport)

    data = await client.get_user("ivan")

    assert data["username"] == "ivan"
    assert data["status"] == "active"


async def test_get_user_returns_none_for_missing_user():
    transport = httpx.MockTransport(_handler_factory(None))
    client = MarzbanClient("https://panel.example.com", "admin", "pass", transport=transport)

    data = await client.get_user("ivan")

    assert data is None


async def test_auth_failure_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "unauthorized"})

    transport = httpx.MockTransport(handler)
    client = MarzbanClient("https://panel.example.com", "admin", "wrong", transport=transport)

    with pytest.raises(MarzbanAuthError):
        await client.get_user("ivan")
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `pytest tests/test_marzban_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bot.marzban.client'`

- [ ] **Step 7: Implement `MarzbanClient`**

`bot/marzban/client.py`:
```python
import time

import httpx


class MarzbanAuthError(Exception):
    pass


class MarzbanClient:
    def __init__(self, base_url: str, username: str, password: str, transport: httpx.BaseTransport | None = None):
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._transport = transport
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=self._transport, timeout=10)

    async def _get_token(self) -> str:
        if self._token and time.monotonic() < self._token_expires_at:
            return self._token
        async with self._client() as client:
            response = await client.post(
                f"{self._base_url}/api/admin/token",
                data={"username": self._username, "password": self._password},
            )
        if response.status_code != 200:
            raise MarzbanAuthError(f"Marzban auth failed: {response.status_code}")
        data = response.json()
        self._token = data["access_token"]
        self._token_expires_at = time.monotonic() + 3000
        return self._token

    async def get_user(self, login: str) -> dict | None:
        token = await self._get_token()
        async with self._client() as client:
            response = await client.get(
                f"{self._base_url}/api/user/{login}",
                headers={"Authorization": f"Bearer {token}"},
            )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `pytest tests/test_marzban_client.py -v`
Expected: PASS (3 tests)

- [ ] **Step 9: Commit**

```bash
git add bot/marzban/__init__.py bot/marzban/client.py bot/marzban/status.py tests/test_marzban_client.py tests/test_marzban_status.py
git commit -m "feat: add Marzban API client and status mapping"
```

---

### Task 8: Renewal reminders job

**Files:**
- Create: `bot/scheduler/__init__.py`
- Create: `bot/scheduler/reminders.py`
- Test: `tests/test_reminders_job.py`

**Interfaces:**
- Consumes: `conn` fixture (Task 2); `users_repo.get_linked_users`, `users_repo.upsert_user`, `users_repo.link_user` (Task 3); `reminders_repo.was_sent` (Task 6); `MarzbanClient`-shaped object with async `get_user(login) -> dict | None` (Task 7, but tests use a fake); `UserStatus` (Task 7).
- Produces: `check_and_send_reminders(conn, marzban, bot, reminder_days: int, now_timestamp: int | None = None) -> int` (returns number of reminders sent; `bot` is any object with async `send_message(chat_id, text)`). Called from `bot/main.py`'s scheduled job.

- [ ] **Step 1: Write the failing tests**

`tests/test_reminders_job.py`:
```python
from bot.db import reminders_repo, users_repo
from bot.scheduler.reminders import check_and_send_reminders

NOW = 1_700_000_000
DAY = 86400


class FakeBot:
    def __init__(self):
        self.sent_messages = []

    async def send_message(self, chat_id, text):
        self.sent_messages.append((chat_id, text))


class FakeMarzban:
    def __init__(self, users):
        self._users = users

    async def get_user(self, login):
        return self._users.get(login)


async def _linked_user(conn, telegram_id, login):
    await users_repo.upsert_user(conn, telegram_id, "user", "User")
    await users_repo.link_user(conn, telegram_id, login)


async def test_sends_reminder_within_threshold(conn):
    await _linked_user(conn, 1, "ivan")
    marzban = FakeMarzban({"ivan": {"status": "active", "used_traffic": 0, "data_limit": None, "expire": NOW + 2 * DAY}})
    bot = FakeBot()

    sent = await check_and_send_reminders(conn, marzban, bot, reminder_days=3, now_timestamp=NOW)

    assert sent == 1
    assert bot.sent_messages[0][0] == 1
    assert await reminders_repo.was_sent(conn, 1, str(NOW + 2 * DAY))


async def test_skips_beyond_threshold(conn):
    await _linked_user(conn, 1, "ivan")
    marzban = FakeMarzban({"ivan": {"status": "active", "used_traffic": 0, "data_limit": None, "expire": NOW + 10 * DAY}})
    bot = FakeBot()

    sent = await check_and_send_reminders(conn, marzban, bot, reminder_days=3, now_timestamp=NOW)

    assert sent == 0
    assert bot.sent_messages == []


async def test_does_not_resend_same_reminder(conn):
    await _linked_user(conn, 1, "ivan")
    marzban = FakeMarzban({"ivan": {"status": "active", "used_traffic": 0, "data_limit": None, "expire": NOW + 2 * DAY}})
    bot = FakeBot()

    await check_and_send_reminders(conn, marzban, bot, reminder_days=3, now_timestamp=NOW)
    sent_second_run = await check_and_send_reminders(conn, marzban, bot, reminder_days=3, now_timestamp=NOW)

    assert sent_second_run == 0
    assert len(bot.sent_messages) == 1


async def test_skips_users_without_expiry(conn):
    await _linked_user(conn, 1, "ivan")
    marzban = FakeMarzban({"ivan": {"status": "active", "used_traffic": 0, "data_limit": None, "expire": None}})
    bot = FakeBot()

    sent = await check_and_send_reminders(conn, marzban, bot, reminder_days=3, now_timestamp=NOW)

    assert sent == 0


async def test_skips_unlinked_users(conn):
    await users_repo.upsert_user(conn, 1, "user", "User")
    marzban = FakeMarzban({})
    bot = FakeBot()

    sent = await check_and_send_reminders(conn, marzban, bot, reminder_days=3, now_timestamp=NOW)

    assert sent == 0
    assert bot.sent_messages == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_reminders_job.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bot.scheduler'`

- [ ] **Step 3: Implement the reminders job**

`bot/scheduler/__init__.py`:
```python
```
(empty file, marks `bot.scheduler` as a package)

`bot/scheduler/reminders.py`:
```python
from datetime import datetime, timezone

from bot.db import reminders_repo, users_repo
from bot.marzban.status import UserStatus


async def check_and_send_reminders(conn, marzban, bot, reminder_days: int, now_timestamp: int | None = None) -> int:
    if now_timestamp is None:
        now_timestamp = int(datetime.now(timezone.utc).timestamp())

    sent_count = 0
    linked_users = await users_repo.get_linked_users(conn)
    for user in linked_users:
        data = await marzban.get_user(user["marzban_login"])
        if data is None:
            continue
        status = UserStatus.from_api(user["marzban_login"], data)
        days_left = status.days_until_expiry(now_timestamp)
        if days_left is None or days_left > reminder_days or days_left < 0:
            continue
        sent_for_date = str(status.expire_timestamp)
        if await reminders_repo.was_sent(conn, user["telegram_id"], sent_for_date):
            continue
        await bot.send_message(
            user["telegram_id"],
            f"Напоминаем: ваша подписка истекает через {days_left} дн. Продлите доступ у администратора.",
        )
        await reminders_repo.mark_sent(conn, user["telegram_id"], sent_for_date)
        sent_count += 1
    return sent_count
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_reminders_job.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add bot/scheduler/__init__.py bot/scheduler/reminders.py tests/test_reminders_job.py
git commit -m "feat: add renewal reminders job"
```

---

### Task 9: Telegram bot handlers & entrypoint

**Files:**
- Create: `bot/filters.py`
- Create: `bot/handlers/__init__.py`
- Create: `bot/handlers/start.py`
- Create: `bot/handlers/complain.py`
- Create: `bot/handlers/status.py`
- Create: `bot/handlers/faq.py`
- Create: `bot/handlers/admin.py`
- Create: `bot/main.py`

**Interfaces:**
- Consumes: `bot.config.load_config` (Task 1); `bot.db.database.open_db` (Task 2); `users_repo`, `complaints_repo`, `link_tokens_repo` (Tasks 3-5); `MarzbanClient`, `UserStatus` (Task 7); `check_and_send_reminders` (Task 8).
- Produces: `bot/main.py` as the process entrypoint (`python -m bot.main`); no other task depends on this one.

This task has no automated tests — per the design spec's testing section, handler wiring is verified manually against a real Telegram bot token and Marzban panel, not with mocked Telegram objects. Steps below are code-writing steps followed by a manual verification checklist.

- [ ] **Step 1: Implement the admin filter**

`bot/filters.py`:
```python
from aiogram.filters import BaseFilter
from aiogram.types import Message


class IsAdmin(BaseFilter):
    def __init__(self, admin_id: int) -> None:
        self.admin_id = admin_id

    async def __call__(self, message: Message) -> bool:
        return message.from_user.id == self.admin_id
```

- [ ] **Step 2: Implement `/start` with deep-link token consumption**

`bot/handlers/__init__.py`:
```python
```
(empty file, marks `bot.handlers` as a package)

`bot/handlers/start.py`:
```python
from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message

from bot.db import link_tokens_repo, users_repo

router = Router(name="start")

WELCOME_TEXT = (
    "Добро пожаловать! Доступные команды:\n"
    "/complain — сообщить о проблеме с VPN\n"
    "/status — статус вашего аккаунта\n"
    "/faq — инструкции по подключению"
)


@router.message(CommandStart())
async def handle_start(message: Message, command: CommandObject, conn) -> None:
    await users_repo.upsert_user(conn, message.from_user.id, message.from_user.username, message.from_user.first_name)

    token = command.args
    if not token:
        await message.answer(WELCOME_TEXT)
        return

    token_row = await link_tokens_repo.get_token(conn, token)
    if token_row is None or token_row["used_at"] is not None:
        await message.answer("Эта ссылка недействительна или уже использована. Запросите новую у администратора.")
        return

    await users_repo.link_user(conn, message.from_user.id, token_row["marzban_login"])
    await link_tokens_repo.mark_used(conn, token, message.from_user.id)
    await message.answer(
        f"Аккаунт привязан к логину {token_row['marzban_login']}. Теперь доступна команда /status.\n\n{WELCOME_TEXT}"
    )
```

- [ ] **Step 3: Implement `/complain`**

`bot/handlers/complain.py`:
```python
from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from bot.db import complaints_repo

router = Router(name="complain")


class ComplainStates(StatesGroup):
    waiting_for_text = State()


@router.message(Command("complain"))
async def handle_complain_start(message: Message, state: FSMContext) -> None:
    await state.set_state(ComplainStates.waiting_for_text)
    await message.answer("Опишите проблему одним сообщением (что не работает, с какого устройства/сервера).")


@router.message(ComplainStates.waiting_for_text)
async def handle_complain_text(message: Message, state: FSMContext, conn, bot: Bot, admin_id: int) -> None:
    complaint_id = await complaints_repo.add_complaint(conn, message.from_user.id, message.text)
    await state.clear()
    await message.answer(f"Жалоба #{complaint_id} зарегистрирована. Спасибо!")

    username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
    await bot.send_message(
        admin_id,
        f"🔴 Жалоба #{complaint_id} от {username} (id {message.from_user.id})\n\n{message.text}",
    )
```

- [ ] **Step 4: Implement `/status`**

`bot/handlers/status.py`:
```python
from datetime import datetime, timezone

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.db import users_repo
from bot.marzban.client import MarzbanClient
from bot.marzban.status import UserStatus

router = Router(name="status")


@router.message(Command("status"))
async def handle_status(message: Message, conn, marzban: MarzbanClient) -> None:
    user = await users_repo.get_user(conn, message.from_user.id)
    if user is None or user["marzban_login"] is None:
        await message.answer("Ваш аккаунт ещё не привязан к панели. Обратитесь к администратору за ссылкой для привязки.")
        return

    try:
        data = await marzban.get_user(user["marzban_login"])
    except Exception:
        await message.answer("Не удалось получить статус, попробуйте позже.")
        return

    if data is None:
        await message.answer("Не удалось получить статус, попробуйте позже.")
        return

    status = UserStatus.from_api(user["marzban_login"], data)
    now_ts = int(datetime.now(timezone.utc).timestamp())
    days_left = status.days_until_expiry(now_ts)

    used_gb = status.used_traffic_bytes / (1024 ** 3)
    limit_text = f"{status.data_limit_bytes / (1024 ** 3):.1f} ГБ" if status.data_limit_bytes else "безлимит"
    expiry_text = f"{days_left} дн." if days_left is not None else "без ограничения"

    await message.answer(
        f"Статус: {status.status}\n"
        f"Трафик: {used_gb:.1f} / {limit_text}\n"
        f"До окончания подписки: {expiry_text}"
    )
```

- [ ] **Step 5: Implement `/faq`**

`bot/handlers/faq.py`:
```python
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

router = Router(name="faq")

FAQ_SECTIONS = {
    "ios": ("iOS", "1. Установите FoXray или Streisand из App Store.\n2. Импортируйте ссылку-подписку.\n3. Включите VPN в приложении."),
    "android": ("Android", "1. Установите NekoBox или v2rayNG из Google Play.\n2. Импортируйте ссылку-подписку.\n3. Подключитесь."),
    "windows": ("Windows", "1. Установите Nekoray или v2rayN.\n2. Импортируйте ссылку-подписку.\n3. Подключитесь."),
    "macos": ("macOS", "1. Установите FoXray или Streisand.\n2. Импортируйте ссылку-подписку.\n3. Подключитесь."),
    "router": ("Роутер", "Настройка зависит от прошивки роутера — обратитесь к администратору за инструкцией под вашу модель."),
}

FAQ_COMMON = (
    "Частые проблемы:\n"
    "— Не устанавливается соединение: проверьте срок подписки командой /status.\n"
    "— Забыли, как подключиться: выберите платформу ниже.\n"
    "— Другая проблема: используйте /complain."
)


def _menu_keyboard() -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=title, callback_data=f"faq:{key}")] for key, (title, _) in FAQ_SECTIONS.items()]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("faq"))
async def handle_faq(message: Message) -> None:
    await message.answer(FAQ_COMMON, reply_markup=_menu_keyboard())


@router.callback_query(lambda c: c.data and c.data.startswith("faq:"))
async def handle_faq_section(callback: CallbackQuery) -> None:
    key = callback.data.split(":", 1)[1]
    if key not in FAQ_SECTIONS:
        await callback.answer()
        return
    title, text = FAQ_SECTIONS[key]
    await callback.message.answer(f"{title}:\n{text}")
    await callback.answer()
```

- [ ] **Step 6: Implement admin commands (`/genlink`, `/broadcast`, `/stats`)**

`bot/handlers/admin.py`:
```python
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Router
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from bot.db import complaints_repo, link_tokens_repo, users_repo
from bot.filters import IsAdmin


def create_admin_router(admin_id: int) -> Router:
    router = Router(name="admin")
    router.message.filter(IsAdmin(admin_id))

    @router.message(Command("genlink"))
    async def handle_genlink(message: Message, command: CommandObject, conn) -> None:
        login = (command.args or "").strip()
        if not login:
            await message.answer("Использование: /genlink <логин_в_панели>")
            return
        token = await link_tokens_repo.create_token(conn, login)
        bot_username = (await message.bot.get_me()).username
        await message.answer(f"Ссылка для {login}:\nhttps://t.me/{bot_username}?start={token}")

    @router.message(Command("broadcast"))
    async def handle_broadcast(message: Message, command: CommandObject, conn, bot: Bot) -> None:
        text = command.args
        if not text:
            await message.answer("Использование: /broadcast <текст сообщения>")
            return

        users = await users_repo.get_all_users(conn)
        delivered = 0
        failed = 0
        for user in users:
            try:
                await bot.send_message(user["telegram_id"], text)
                delivered += 1
            except TelegramForbiddenError:
                failed += 1

        await message.answer(f"Рассылка завершена. Доставлено: {delivered}, не доставлено: {failed}")

    @router.message(Command("stats"))
    async def handle_stats(message: Message, conn) -> None:
        total = await complaints_repo.count_all(conn)
        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        last_week = await complaints_repo.count_since(conn, week_ago)
        by_user = await complaints_repo.count_by_user(conn)

        lines = [f"Всего жалоб: {total}", f"За последние 7 дней: {last_week}", "", "По пользователям:"]
        for row in by_user:
            lines.append(f"  {row['telegram_id']}: {row['cnt']}")

        await message.answer("\n".join(lines))

    return router
```

- [ ] **Step 7: Wire everything in the entrypoint**

`bot/main.py`:
```python
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.config import load_config
from bot.db.database import open_db
from bot.handlers import admin, complain, faq, start, status
from bot.marzban.client import MarzbanClient
from bot.scheduler.reminders import check_and_send_reminders

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    config = load_config()
    conn = await open_db(config.db_path)
    marzban = MarzbanClient(config.marzban_url, config.marzban_username, config.marzban_password)

    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(start.router)
    dp.include_router(complain.router)
    dp.include_router(status.router)
    dp.include_router(faq.router)
    dp.include_router(admin.create_admin_router(config.admin_id))

    scheduler = AsyncIOScheduler()

    async def reminders_job() -> None:
        try:
            sent = await check_and_send_reminders(conn, marzban, bot, config.reminder_days)
            logger.info("Reminder job sent %d reminders", sent)
        except Exception:
            logger.exception("Reminder job failed")

    scheduler.add_job(reminders_job, "cron", hour=10, minute=0)
    scheduler.start()

    try:
        await dp.start_polling(bot, conn=conn, marzban=marzban, admin_id=config.admin_id)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 8: Commit**

```bash
git add bot/filters.py bot/handlers/__init__.py bot/handlers/start.py bot/handlers/complain.py bot/handlers/status.py bot/handlers/faq.py bot/handlers/admin.py bot/main.py
git commit -m "feat: add Telegram handlers and bot entrypoint"
```

- [ ] **Step 9: Manual verification (requires a real bot token, your Telegram ID, and Marzban credentials)**

Fill `.env` (copy from `.env.example`) with real `BOT_TOKEN`, `ADMIN_ID` (your numeric Telegram ID — get it from @userinfobot), `MARZBAN_URL`/`MARZBAN_USERNAME`/`MARZBAN_PASSWORD`. Then:

```bash
pip install -r requirements.txt
python -m bot.main
```

Checklist, in order:
1. From a non-admin Telegram account, send `/start` → expect the welcome text with the 3 commands listed.
2. From your admin account, send `/genlink <существующий_логин_в_панели>` → expect a `https://t.me/<bot>?start=LNK_...` link back.
3. Open that link from the non-admin account → expect "Аккаунт привязан к логину ..." confirmation.
4. Open the same link again → expect "недействительна или уже использована".
5. From the linked non-admin account, send `/status` → expect real traffic/expiry data from the panel.
6. From the non-admin account, send `/complain`, then describe a problem → expect a confirmation with a complaint number, and check that your admin account receives the forwarded complaint.
7. Send `/faq` → expect inline platform buttons; tap one → expect the instructions text.
8. From the admin account, send `/broadcast Тестовое сообщение` → expect a delivered/failed count, and confirm the non-admin account received the broadcast.
9. From the admin account, send `/stats` → expect totals that match what you generated above.

---

### Task 10: Docker packaging

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`

**Interfaces:**
- Consumes: `requirements.txt` (Task 1), `bot/main.py` (Task 9) as the container's entrypoint.
- Produces: a buildable container image; nothing else depends on this task.

- [ ] **Step 1: Write the Dockerfile**

`Dockerfile`:
```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot ./bot

CMD ["python", "-m", "bot.main"]
```

- [ ] **Step 2: Write docker-compose.yml**

`docker-compose.yml`:
```yaml
services:
  bot:
    build: .
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./data:/app/data
```

- [ ] **Step 3: Validate the compose file if Docker is available locally**

Run: `docker compose config`
Expected: prints the resolved config with no errors. If Docker isn't installed on the dev machine, skip this step — it will be validated for real on the Ubuntu server in the next step.

- [ ] **Step 4: Commit**

```bash
git add Dockerfile docker-compose.yml
git commit -m "feat: add Docker packaging for deployment"
```

- [ ] **Step 5: Deploy on the Ubuntu server (manual — run this yourself over SSH, not part of this coding session)**

```bash
git clone https://github.com/melekhov-sa/obrSvaz.git
cd obrSvaz
cp .env.example .env
nano .env   # заполнить BOT_TOKEN, ADMIN_ID, MARZBAN_URL/USERNAME/PASSWORD
docker compose up -d --build
docker compose logs -f bot
```

Confirm in the logs that polling starts without errors, then repeat the Task 9 manual checklist against the deployed instance.

---

## Self-Review Notes

- **Spec coverage:** жалобы → Task 4 + Task 9 (`/complain`); напоминания о продлении → Task 6 + Task 8 + Task 9 scheduler wiring; токен-привязка → Task 5 + Task 9 (`/genlink`, `/start`); `/status` → Task 9; FAQ → Task 9; `/broadcast` → Task 9; `/stats` → Task 4 + Task 9; деплой → Task 10. All spec sections are covered.
- **Placeholder scan:** no TBD/TODO markers; every step has complete, runnable code.
- **Type consistency:** repo function names and signatures (`upsert_user`, `get_user`, `link_user`, `get_all_users`, `get_linked_users`, `add_complaint`, `count_all`, `count_since`, `count_by_user`, `generate_token`, `create_token`, `get_token`, `mark_used`, `was_sent`, `mark_sent`, `check_and_send_reminders`, `MarzbanClient.get_user`, `UserStatus.from_api`, `UserStatus.days_until_expiry`) are identical everywhere they're defined and consumed across Tasks 3-9.
