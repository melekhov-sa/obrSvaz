# Admin Tools Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the bot's admin (a) user counts in `/stats`, (b) a Telegram command menu that shows admin-only commands only in the admin's chat, and (c) an `/unlink <login>` command to remove an accidental or stale account link.

**Architecture:** Small additive changes to the already-shipped bot (Python 3.12 + aiogram 3, SQLite via aiosqlite). One new repository function (`unlink_by_login`), two handler/wiring edits. No new modules, no schema changes.

**Tech Stack:** Same as the base project — aiogram 3, aiosqlite, pytest + pytest-asyncio.

## Global Constraints

- `/unlink` is admin-only, lives in `create_admin_router` alongside `/genlink`, `/broadcast`, `/stats` (same file, same factory function — not a new router).
- `/unlink <login>` operates on `marzban_login`, never `telegram_id` — consistent with `/genlink <login>` already using logins as the handle (per the design spec's "Вне рамок" decision).
- Handler-layer changes (admin.py, main.py) get NO new automated tests — this project's design spec deliberately scopes automated tests to the DB/Marzban/scheduler layers only; handlers are manually verified. This is not a gap in this plan, it's the established pattern (see `docs/superpowers/specs/2026-07-22-vpn-feedback-bot-design.md`'s Тестирование section).
- The new DB function (`unlink_by_login`) DOES get a unit test, following the exact pattern of the other functions in `bot/db/users_repo.py` (real in-memory SQLite via the `conn` fixture, no mocks).
- Command menu registration uses aiogram's `BotCommandScopeDefault` (public) and `BotCommandScopeChat` (admin-only) — set once at startup in `bot/main.py`, not per-message.

---

### Task 1: `unlink_by_login` in the users repository

**Files:**
- Modify: `bot/db/users_repo.py`
- Test: `tests/test_users_repo.py`

**Interfaces:**
- Consumes: nothing new — same `conn: aiosqlite.Connection` (row_factory already `aiosqlite.Row`) used by every function in this file.
- Produces: `unlink_by_login(conn, marzban_login: str) -> aiosqlite.Row | None`. Returns the user row that was unlinked (so the caller can report which `telegram_id` lost the link), or `None` if no user currently holds that login. Used by Task 2's `/unlink` handler.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_users_repo.py` (the file already imports `from bot.db import users_repo` at the top — don't duplicate that import):

```python
async def test_unlink_by_login_clears_fields_and_returns_row(conn):
    await users_repo.upsert_user(conn, 1, "ivan", "Ivan")
    await users_repo.link_user(conn, 1, "ivan_login")

    row = await users_repo.unlink_by_login(conn, "ivan_login")

    assert row["telegram_id"] == 1
    user = await users_repo.get_user(conn, 1)
    assert user["marzban_login"] is None
    assert user["linked_at"] is None


async def test_unlink_by_login_returns_none_when_not_found(conn):
    row = await users_repo.unlink_by_login(conn, "nonexistent_login")
    assert row is None


async def test_unlink_by_login_does_not_affect_other_users(conn):
    await users_repo.upsert_user(conn, 1, "ivan", "Ivan")
    await users_repo.upsert_user(conn, 2, "petr", "Petr")
    await users_repo.link_user(conn, 1, "ivan_login")
    await users_repo.link_user(conn, 2, "petr_login")

    await users_repo.unlink_by_login(conn, "ivan_login")

    petr = await users_repo.get_user(conn, 2)
    assert petr["marzban_login"] == "petr_login"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_users_repo.py -v -k unlink_by_login`
Expected: FAIL with `AttributeError: module 'bot.db.users_repo' has no attribute 'unlink_by_login'`

- [ ] **Step 3: Implement `unlink_by_login`**

Add to the end of `bot/db/users_repo.py` (after the existing `get_linked_users` function):

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_users_repo.py -v`
Expected: PASS (10 tests: the 7 existing plus the 3 new ones)

- [ ] **Step 5: Run the full suite to confirm no regressions**

Run: `pytest -q`
Expected: PASS (36 passed — 33 existing + 3 new)

- [ ] **Step 6: Commit**

```bash
git add bot/db/users_repo.py tests/test_users_repo.py
git commit -m "feat: add unlink_by_login to users repository"
```

---

### Task 2: `/unlink` command, `/stats` user counts, Telegram command menu

**Files:**
- Modify: `bot/handlers/admin.py`
- Modify: `bot/main.py`

**Interfaces:**
- Consumes: `users_repo.unlink_by_login` (Task 1), `users_repo.get_all_users`/`get_linked_users` (already existed, used by `/broadcast` and this task's `/stats` change).
- Produces: nothing new consumed by later tasks — this is the last task in this plan.

No automated tests for this task (handler/wiring layer — see Global Constraints). Verify with the manual checklist in Step 4.

- [ ] **Step 1: Extend `/stats` with user counts**

In `bot/handlers/admin.py`, replace the `handle_stats` function body (currently lines 44-55) with:

```python
    @router.message(Command("stats"))
    async def handle_stats(message: Message, conn) -> None:
        all_users = await users_repo.get_all_users(conn)
        linked_users = await users_repo.get_linked_users(conn)
        total = await complaints_repo.count_all(conn)
        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        last_week = await complaints_repo.count_since(conn, week_ago)
        by_user = await complaints_repo.count_by_user(conn)

        lines = [
            f"Зарегистрировано в боте: {len(all_users)}",
            f"Привязано к панели: {len(linked_users)}",
            "",
            f"Всего жалоб: {total}",
            f"За последние 7 дней: {last_week}",
            "",
            "По пользователям:",
        ]
        for row in by_user:
            lines.append(f"  {row['telegram_id']}: {row['cnt']}")

        await message.answer("\n".join(lines))
```

No new imports needed — `users_repo` is already imported at the top of this file (line 7).

- [ ] **Step 2: Add the `/unlink` command**

In `bot/handlers/admin.py`, add a new handler right after `handle_genlink` (after line 23, before the blank line preceding `handle_broadcast`):

```python
    @router.message(Command("unlink"))
    async def handle_unlink(message: Message, command: CommandObject, conn) -> None:
        login = (command.args or "").strip()
        if not login:
            await message.answer("Использование: /unlink <логин_в_панели>")
            return
        row = await users_repo.unlink_by_login(conn, login)
        if row is None:
            await message.answer(f"Активной привязки для логина {login} не найдено.")
            return
        await message.answer(f"Отвязано: {login} (был привязан к id {row['telegram_id']})")
```

- [ ] **Step 3: Register the Telegram command menu**

In `bot/main.py`:

1. Add to the import block at the top (after the existing `from aiogram import Bot, Dispatcher` line):

```python
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault
```

2. In the `main()` function, right after the line `bot = Bot(token=config.bot_token)` and before `dp = Dispatcher(storage=MemoryStorage())`, insert:

```python
    public_commands = [
        BotCommand(command="complain", description="Сообщить о проблеме с VPN"),
        BotCommand(command="status", description="Статус вашего аккаунта"),
        BotCommand(command="faq", description="Инструкции по подключению"),
    ]
    admin_commands = public_commands + [
        BotCommand(command="genlink", description="Сгенерировать ссылку для привязки"),
        BotCommand(command="unlink", description="Снять привязку пользователя"),
        BotCommand(command="broadcast", description="Разослать сообщение всем"),
        BotCommand(command="stats", description="Статистика"),
    ]
    await bot.set_my_commands(public_commands, scope=BotCommandScopeDefault())
    await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=config.admin_id))
```

The resulting order in `main()` should be: create `bot` → set the two command menus → create `dp` → include routers → scheduler setup → `start_polling`.

- [ ] **Step 4: Verify and commit**

Run the import sanity check and full suite (these confirm the edits don't break anything already covered — they do NOT test the new `/unlink`/`/stats`/menu behavior itself, which needs the manual checklist below):

Run: `python -c "import bot.main"` (or `py -3.13 -c "import bot.main"` — use whatever invocation worked for Task 9 in this environment)
Expected: no output, exit code 0 (import succeeds)

Run: `pytest -q`
Expected: `36 passed` (same count as end of Task 1 — this task adds no tests)

```bash
git add bot/handlers/admin.py bot/main.py
git commit -m "feat: add /unlink command, /stats user counts, Telegram command menu"
```

- [ ] **Step 5: Manual verification checklist (run after deploying, with a real bot token/admin chat)**

1. Restart the bot (`docker compose up -d --force-recreate` on the server, or re-run locally) so `set_my_commands` executes.
2. Open the bot chat from your admin account, tap the "/" menu button — should show `complain`, `status`, `faq`, `genlink`, `unlink`, `broadcast`, `stats` (7 items).
3. Open the bot chat from a non-admin account, tap "/" — should show only `complain`, `status`, `faq` (3 items).
4. From the admin account: `/genlink <a real login>`, follow the link from a test account to link it, then `/unlink <that login>` — expect `Отвязано: <login> (был привязан к id <telegram_id>)`. Confirm with `/status` on the test account that it now reports "не привязан".
5. `/unlink <a login nobody currently holds>` — expect `Активной привязки для логина <login> не найдено.`
6. `/stats` — expect the new "Зарегистрировано в боте: N" / "Привязано к панели: M" lines above the existing complaint stats, with numbers matching what you'd expect from your test accounts.

---

## Self-Review Notes

- **Spec coverage:** `/stats` user counts → Task 2 Step 1; command menu (public/admin scopes) → Task 2 Step 3; `/unlink <login>` → Task 1 (repo function) + Task 2 Step 2 (handler). All three spec sections covered.
- **Placeholder scan:** no TBD/TODO; every step has complete code matching the actual current contents of `bot/handlers/admin.py` and `bot/main.py` (read directly from the worktree before writing this plan).
- **Type consistency:** `unlink_by_login(conn, marzban_login: str) -> aiosqlite.Row | None` is defined once in Task 1 and consumed with that exact name/shape in Task 2 Step 2 (`row = await users_repo.unlink_by_login(conn, login)`, then `row["telegram_id"]`).
