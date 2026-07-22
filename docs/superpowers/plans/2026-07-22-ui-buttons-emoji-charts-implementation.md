# UI Buttons, Emoji, and Text Charts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an inline-button main menu, a consistent emoji vocabulary, a text bar-chart of daily complaints in `/stats`, and a text usage bar in `/status` to the already-deployed VPN feedback bot — all additive UX polish, no business-logic changes.

**Architecture:** Two new pure-function/data pieces (`bot/formatting.py`, `complaints_repo.count_by_day`), then each existing handler file is rewritten to its final state (emoji + wiring), then a new `bot/handlers/menu.py` ties everything together behind inline buttons, reusing logic extracted from the handler rewrites rather than duplicating it.

**Tech Stack:** Same as the deployed project — Python 3.12, aiogram 3, aiosqlite, pytest + pytest-asyncio. No new dependencies.

## Global Constraints

- No new pip dependencies (spec explicitly rejected matplotlib/image-based charts in favor of Unicode text bars).
- Bar width is 10 characters everywhere (`█` filled / `░` empty); complaint chart covers the last 14 days.
- Emoji vocabulary (use exactly these, don't invent variants): 🔴 new complaint, ✅ success/confirmation, ⚠️ warning/error/usage-hint, 🌐 VPN status, 📊/📈 stats, 🔗 link (`/genlink`), 🔓 unlink, 📢 broadcast, 📖 FAQ, ⏳ expiry.
- Text commands (`/complain`, `/status`, `/faq`, `/stats`, `/genlink`, `/broadcast`, `/unlink`) keep working exactly as before — buttons are an additional entry point, not a replacement.
- Handler-layer files (`bot/handlers/*.py`, `bot/main.py`) get NO new automated tests — established project policy, verified manually. Only `bot/formatting.py` and `bot/db/complaints_repo.py` (pure/data functions) get unit tests, following the exact pattern already used throughout `tests/`.
- `render_usage_bar` returns `None` when there's no data limit (caller must handle `None` by omitting the bar, not crashing); usage over 100% is shown uncapped, not clamped.
- `render_daily_bar_chart` must not divide by zero when every day in the window has 0 complaints.

## File Structure

```
bot/
  formatting.py               # NEW — pure rendering functions, no I/O
  db/
    complaints_repo.py         # + count_by_day()
  handlers/
    status.py                  # rewritten: + build_status_text(), usage bar, emoji
    faq.py                     # rewritten: emoji, _menu_keyboard -> public faq_keyboard()
    complain.py                # rewritten: emoji, + start_complaint_flow(), COMPLAIN_PROMPT
    admin.py                   # rewritten: emoji, + build_stats_text(), daily chart
    menu.py                    # NEW — main_menu_keyboard(), /menu command, menu:* callbacks
    start.py                   # rewritten: emoji, attaches main_menu_keyboard()
  main.py                      # + menu router, /menu in command list
tests/
  test_formatting.py           # NEW
  test_complaints_repo.py      # + count_by_day tests
```

Tasks are ordered so each file is touched exactly once, and later tasks only depend on names introduced by earlier tasks (never the reverse).

---

### Task 1: `bot/formatting.py` — pure rendering functions

**Files:**
- Create: `bot/formatting.py`
- Test: `tests/test_formatting.py`

**Interfaces:**
- Consumes: nothing (pure functions, no DB/network).
- Produces: `render_daily_bar_chart(counts_by_day: dict[str, int], days: int) -> str` and `render_usage_bar(used_bytes: int, limit_bytes: int | None, width: int = 10) -> str | None`. Used by Task 6 (`admin.py`) and Task 3 (`status.py`) respectively.

- [ ] **Step 1: Write the failing tests**

`tests/test_formatting.py`:
```python
from datetime import datetime, timedelta, timezone

from bot.formatting import render_daily_bar_chart, render_usage_bar


def test_render_daily_bar_chart_shows_all_zero_when_no_complaints():
    result = render_daily_bar_chart({}, days=3)

    lines = result.split("\n")
    assert len(lines) == 3
    for line in lines:
        assert line.endswith(" 0")
        assert "█" not in line


def test_render_daily_bar_chart_scales_bars_to_peak():
    today = datetime.now(timezone.utc).date()
    counts = {
        today.isoformat(): 10,
        (today - timedelta(days=1)).isoformat(): 5,
    }

    result = render_daily_bar_chart(counts, days=2)

    lines = result.split("\n")
    assert lines[0].endswith(" 5")
    assert lines[1].endswith(" 10")
    assert lines[0].count("█") == 5
    assert lines[1].count("█") == 10


def test_render_daily_bar_chart_orders_oldest_to_newest():
    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)
    counts = {today.isoformat(): 1, yesterday.isoformat(): 2}

    result = render_daily_bar_chart(counts, days=2)

    lines = result.split("\n")
    assert lines[0].startswith(yesterday.strftime("%d.%m"))
    assert lines[1].startswith(today.strftime("%d.%m"))


def test_render_usage_bar_returns_none_when_no_limit():
    assert render_usage_bar(used_bytes=1000, limit_bytes=None) is None
    assert render_usage_bar(used_bytes=1000, limit_bytes=0) is None


def test_render_usage_bar_shows_percentage_and_gb():
    limit = 50 * 1024 ** 3
    used = 34 * 1024 ** 3 + int(0.2 * 1024 ** 3)

    result = render_usage_bar(used_bytes=used, limit_bytes=limit)

    assert "68%" in result
    assert "34.2" in result
    assert "50.0" in result


def test_render_usage_bar_over_100_percent_not_clamped():
    limit = 50 * 1024 ** 3
    used = 60 * 1024 ** 3

    result = render_usage_bar(used_bytes=used, limit_bytes=limit)

    assert "120%" in result
    assert result.count("█") == 10
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_formatting.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bot.formatting'`

- [ ] **Step 3: Implement**

`bot/formatting.py`:
```python
from datetime import datetime, timedelta, timezone

BAR_WIDTH = 10


def render_daily_bar_chart(counts_by_day: dict[str, int], days: int) -> str:
    today = datetime.now(timezone.utc).date()
    ordered_days = [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]
    values = [counts_by_day.get(day.isoformat(), 0) for day in ordered_days]
    peak = max(values) if values else 0

    lines = []
    for day, value in zip(ordered_days, values):
        filled = round((value / peak) * BAR_WIDTH) if peak > 0 else 0
        bar = "█" * filled + "░" * (BAR_WIDTH - filled)
        lines.append(f"{day.strftime('%d.%m')} {bar} {value}")
    return "\n".join(lines)


def render_usage_bar(used_bytes: int, limit_bytes: int | None, width: int = BAR_WIDTH) -> str | None:
    if not limit_bytes:
        return None

    used_gb = used_bytes / (1024 ** 3)
    limit_gb = limit_bytes / (1024 ** 3)
    ratio = used_bytes / limit_bytes
    filled = min(width, round(ratio * width))
    bar = "█" * filled + "░" * (width - filled)
    percent = round(ratio * 100)
    return f"[{bar}] {percent}% ({used_gb:.1f} / {limit_gb:.1f} ГБ)"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_formatting.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Run the full suite to confirm no regressions**

Run: `pytest -q`
Expected: `42 passed` (36 existing + 6 new)

- [ ] **Step 6: Commit**

```bash
git add bot/formatting.py tests/test_formatting.py
git commit -m "feat: add text-based chart and usage-bar formatting helpers"
```

---

### Task 2: `count_by_day` in complaints repository

**Files:**
- Modify: `bot/db/complaints_repo.py`
- Test: `tests/test_complaints_repo.py`

**Interfaces:**
- Consumes: `conn` fixture (existing); `users_repo.upsert_user` (existing, for test setup).
- Produces: `count_by_day(conn, since_iso: str) -> list[aiosqlite.Row]`, rows shaped `(day: str "YYYY-MM-DD", cnt: int)`. Used by Task 6 (`admin.py`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_complaints_repo.py` (file already imports `complaints_repo`, `users_repo`, and `datetime`/`timedelta`/`timezone` — reuse those, don't re-import):

```python
async def test_count_by_day_groups_by_date(conn):
    await users_repo.upsert_user(conn, 1, "ivan", "Ivan")
    await complaints_repo.add_complaint(conn, 1, "a")
    await complaints_repo.add_complaint(conn, 1, "b")

    since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    rows = await complaints_repo.count_by_day(conn, since)

    assert len(rows) == 1
    today = datetime.now(timezone.utc).date().isoformat()
    assert rows[0]["day"] == today
    assert rows[0]["cnt"] == 2


async def test_count_by_day_excludes_old_complaints(conn):
    await users_repo.upsert_user(conn, 1, "ivan", "Ivan")
    await complaints_repo.add_complaint(conn, 1, "a")

    future_cutoff = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    rows = await complaints_repo.count_by_day(conn, future_cutoff)

    assert rows == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_complaints_repo.py -v -k count_by_day`
Expected: FAIL with `AttributeError: module 'bot.db.complaints_repo' has no attribute 'count_by_day'`

- [ ] **Step 3: Implement**

Add to the end of `bot/db/complaints_repo.py`. Uses `substr(created_at, 1, 10)` rather than SQLite's `DATE()` function — `created_at` is always stored via Python's `datetime.isoformat()` on a UTC-aware datetime, so the first 10 characters are always exactly `YYYY-MM-DD`; a plain substring is version-independent and avoids relying on how a given SQLite build parses ISO-8601-with-timezone-offset strings:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_complaints_repo.py -v`
Expected: PASS (6 tests: 4 existing + 2 new)

- [ ] **Step 5: Run the full suite to confirm no regressions**

Run: `pytest -q`
Expected: `44 passed` (42 from Task 1 + 2 new)

- [ ] **Step 6: Commit**

```bash
git add bot/db/complaints_repo.py tests/test_complaints_repo.py
git commit -m "feat: add count_by_day to complaints repository"
```

---

### Task 3: Rewrite `bot/handlers/status.py` — emoji + usage bar

**Files:**
- Modify: `bot/handlers/status.py` (full-file rewrite)

**Interfaces:**
- Consumes: `render_usage_bar` (Task 1); `users_repo.get_user` (existing); `MarzbanClient`, `UserStatus` (existing).
- Produces: `build_status_text(conn, marzban: MarzbanClient, telegram_id: int) -> str` — the message body as plain text, with no side effects (doesn't send anything itself). Used by Task 7 (`menu.py`'s `menu:status` callback) and by this file's own `handle_status`.

No automated tests for this task (handler layer — see Global Constraints).

- [ ] **Step 1: Replace the entire file**

`bot/handlers/status.py`:
```python
from datetime import datetime, timezone

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.db import users_repo
from bot.formatting import render_usage_bar
from bot.marzban.client import MarzbanClient
from bot.marzban.status import UserStatus

router = Router(name="status")


async def build_status_text(conn, marzban: MarzbanClient, telegram_id: int) -> str:
    user = await users_repo.get_user(conn, telegram_id)
    if user is None or user["marzban_login"] is None:
        return "⚠️ Ваш аккаунт ещё не привязан к панели. Обратитесь к администратору за ссылкой для привязки."

    try:
        data = await marzban.get_user(user["marzban_login"])
    except Exception:
        return "⚠️ Не удалось получить статус, попробуйте позже."

    if data is None:
        return "⚠️ Не удалось получить статус, попробуйте позже."

    status = UserStatus.from_api(user["marzban_login"], data)
    now_ts = int(datetime.now(timezone.utc).timestamp())
    days_left = status.days_until_expiry(now_ts)

    used_gb = status.used_traffic_bytes / (1024 ** 3)
    limit_text = f"{status.data_limit_bytes / (1024 ** 3):.1f} ГБ" if status.data_limit_bytes else "безлимит"
    expiry_text = f"{days_left} дн." if days_left is not None else "без ограничения"

    lines = [
        f"🌐 Статус: {status.status}",
        f"Трафик: {used_gb:.1f} / {limit_text}",
        f"⏳ До окончания подписки: {expiry_text}",
    ]

    usage_bar = render_usage_bar(status.used_traffic_bytes, status.data_limit_bytes)
    if usage_bar is not None:
        lines.append(usage_bar)

    return "\n".join(lines)


@router.message(Command("status"))
async def handle_status(message: Message, conn, marzban: MarzbanClient) -> None:
    text = await build_status_text(conn, marzban, message.from_user.id)
    await message.answer(text)
```

- [ ] **Step 2: Run the import sanity check**

Run: `python -c "import bot.main"` (or `py -3.13 -c "import bot.main"` — use whatever invocation has worked in this environment)
Expected: no output, exit code 0

- [ ] **Step 3: Run the full suite to confirm no regressions**

Run: `pytest -q`
Expected: `44 passed` (unchanged from Task 2 — this task adds no tests)

- [ ] **Step 4: Commit**

```bash
git add bot/handlers/status.py
git commit -m "feat: add usage bar and emoji to /status"
```

---

### Task 4: Rewrite `bot/handlers/faq.py` — emoji + public keyboard function

**Files:**
- Modify: `bot/handlers/faq.py` (full-file rewrite)

**Interfaces:**
- Consumes: nothing new.
- Produces: `faq_keyboard() -> InlineKeyboardMarkup` (renamed from the previously-private `_menu_keyboard`) and the module-level constant `FAQ_COMMON: str`. Both used by Task 7 (`menu.py`'s `menu:faq` callback).

No automated tests for this task (handler layer).

- [ ] **Step 1: Replace the entire file**

`bot/handlers/faq.py`:
```python
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

router = Router(name="faq")

FAQ_SECTIONS = {
    "ios": ("📱 iOS", "1. Установите FoXray или Streisand из App Store.\n2. Импортируйте ссылку-подписку.\n3. Включите VPN в приложении."),
    "android": ("🤖 Android", "1. Установите NekoBox или v2rayNG из Google Play.\n2. Импортируйте ссылку-подписку.\n3. Подключитесь."),
    "windows": ("🪟 Windows", "1. Установите Nekoray или v2rayN.\n2. Импортируйте ссылку-подписку.\n3. Подключитесь."),
    "macos": ("🍎 macOS", "1. Установите FoXray или Streisand.\n2. Импортируйте ссылку-подписку.\n3. Подключитесь."),
    "router": ("📶 Роутер", "Настройка зависит от прошивки роутера — обратитесь к администратору за инструкцией под вашу модель."),
}

FAQ_COMMON = (
    "📖 Частые проблемы:\n"
    "— Не устанавливается соединение: проверьте срок подписки командой /status.\n"
    "— Забыли, как подключиться: выберите платформу ниже.\n"
    "— Другая проблема: используйте /complain."
)


def faq_keyboard() -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=title, callback_data=f"faq:{key}")] for key, (title, _) in FAQ_SECTIONS.items()]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("faq"))
async def handle_faq(message: Message) -> None:
    await message.answer(FAQ_COMMON, reply_markup=faq_keyboard())


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

- [ ] **Step 2: Run the import sanity check**

Run: `python -c "import bot.main"`
Expected: exit code 0

- [ ] **Step 3: Run the full suite to confirm no regressions**

Run: `pytest -q`
Expected: `44 passed`

- [ ] **Step 4: Commit**

```bash
git add bot/handlers/faq.py
git commit -m "feat: add emoji to FAQ, expose public faq_keyboard()"
```

---

### Task 5: Rewrite `bot/handlers/complain.py` — emoji + reusable flow starter

**Files:**
- Modify: `bot/handlers/complain.py` (full-file rewrite)

**Interfaces:**
- Consumes: nothing new.
- Produces: `COMPLAIN_PROMPT: str` and `start_complaint_flow(state: FSMContext) -> None` (sets the FSM state only, sends no message). Both used by Task 7 (`menu.py`'s `menu:complain` callback).

No automated tests for this task (handler layer).

- [ ] **Step 1: Replace the entire file**

`bot/handlers/complain.py`:
```python
from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from bot.db import complaints_repo

router = Router(name="complain")

COMPLAIN_PROMPT = "🔴 Опишите проблему одним сообщением (что не работает, с какого устройства/сервера)."


class ComplainStates(StatesGroup):
    waiting_for_text = State()


async def start_complaint_flow(state: FSMContext) -> None:
    await state.set_state(ComplainStates.waiting_for_text)


@router.message(Command("complain"))
async def handle_complain_start(message: Message, state: FSMContext) -> None:
    await start_complaint_flow(state)
    await message.answer(COMPLAIN_PROMPT)


@router.message(ComplainStates.waiting_for_text, F.text, ~F.text.startswith("/"))
async def handle_complain_text(message: Message, state: FSMContext, conn, bot: Bot, admin_id: int) -> None:
    complaint_id = await complaints_repo.add_complaint(conn, message.from_user.id, message.text)
    await state.clear()
    await message.answer(f"✅ Жалоба #{complaint_id} зарегистрирована. Спасибо!")

    username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
    await bot.send_message(
        admin_id,
        f"🔴 Жалоба #{complaint_id} от {username} (id {message.from_user.id})\n\n{message.text}",
    )
```

- [ ] **Step 2: Run the import sanity check**

Run: `python -c "import bot.main"`
Expected: exit code 0

- [ ] **Step 3: Run the full suite to confirm no regressions**

Run: `pytest -q`
Expected: `44 passed`

- [ ] **Step 4: Commit**

```bash
git add bot/handlers/complain.py
git commit -m "feat: add emoji to /complain, expose reusable flow starter"
```

---

### Task 6: Rewrite `bot/handlers/admin.py` — emoji + complaint bar chart

**Files:**
- Modify: `bot/handlers/admin.py` (full-file rewrite)

**Interfaces:**
- Consumes: `render_daily_bar_chart` (Task 1); `complaints_repo.count_by_day` (Task 2); `users_repo`, `complaints_repo.count_all/count_since/count_by_user`, `link_tokens_repo`, `IsAdmin` (all existing, unchanged).
- Produces: `build_stats_text(conn) -> str` — a MODULE-LEVEL function (not inside `create_admin_router`, since it needs no `admin_id`), returning the full `/stats` message body. Used by Task 7 (`menu.py`'s `menu:stats` callback) and by this file's own `handle_stats`. `create_admin_router(admin_id: int) -> Router` keeps its existing signature — no caller elsewhere needs to change.

No automated tests for this task (handler layer).

- [ ] **Step 1: Replace the entire file**

`bot/handlers/admin.py`:
```python
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from bot.db import complaints_repo, link_tokens_repo, users_repo
from bot.filters import IsAdmin
from bot.formatting import render_daily_bar_chart

CHART_DAYS = 14


async def build_stats_text(conn) -> str:
    all_users = await users_repo.get_all_users(conn)
    linked_users = await users_repo.get_linked_users(conn)
    total = await complaints_repo.count_all(conn)
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    last_week = await complaints_repo.count_since(conn, week_ago)
    by_user = await complaints_repo.count_by_user(conn)

    since = (datetime.now(timezone.utc) - timedelta(days=CHART_DAYS)).isoformat()
    by_day_rows = await complaints_repo.count_by_day(conn, since)
    counts_by_day = {row["day"]: row["cnt"] for row in by_day_rows}

    lines = [
        "📊 Статистика",
        "",
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

    lines.append("")
    lines.append(f"📈 Жалобы за {CHART_DAYS} дней:")
    lines.append(render_daily_bar_chart(counts_by_day, CHART_DAYS))

    return "\n".join(lines)


def create_admin_router(admin_id: int) -> Router:
    router = Router(name="admin")
    router.message.filter(IsAdmin(admin_id))

    @router.message(Command("genlink"))
    async def handle_genlink(message: Message, command: CommandObject, conn) -> None:
        login = (command.args or "").strip()
        if not login:
            await message.answer("⚠️ Использование: /genlink <логин_в_панели>")
            return
        token = await link_tokens_repo.create_token(conn, login)
        bot_username = (await message.bot.get_me()).username
        await message.answer(f"🔗 Ссылка для {login}:\nhttps://t.me/{bot_username}?start={token}")

    @router.message(Command("unlink"))
    async def handle_unlink(message: Message, command: CommandObject, conn) -> None:
        login = (command.args or "").strip()
        if not login:
            await message.answer("⚠️ Использование: /unlink <логин_в_панели>")
            return
        row = await users_repo.unlink_by_login(conn, login)
        if row is None:
            await message.answer(f"⚠️ Активной привязки для логина {login} не найдено.")
            return
        await message.answer(f"🔓 Отвязано: {login} (был привязан к id {row['telegram_id']})")

    @router.message(Command("broadcast"))
    async def handle_broadcast(message: Message, command: CommandObject, conn, bot: Bot) -> None:
        text = command.args
        if not text:
            await message.answer("⚠️ Использование: /broadcast <текст сообщения>")
            return

        users = await users_repo.get_all_users(conn)
        delivered = 0
        failed = 0
        for user in users:
            try:
                await bot.send_message(user["telegram_id"], text)
                delivered += 1
            except Exception:
                failed += 1

        await message.answer(f"📢 Рассылка завершена. Доставлено: {delivered}, не доставлено: {failed}")

    @router.message(Command("stats"))
    async def handle_stats(message: Message, conn) -> None:
        text = await build_stats_text(conn)
        await message.answer(text)

    return router
```

- [ ] **Step 2: Run the import sanity check**

Run: `python -c "import bot.main"`
Expected: exit code 0

- [ ] **Step 3: Run the full suite to confirm no regressions**

Run: `pytest -q`
Expected: `44 passed`

- [ ] **Step 4: Commit**

```bash
git add bot/handlers/admin.py
git commit -m "feat: add daily complaint bar chart and emoji to admin commands"
```

---

### Task 7: Main menu — `bot/handlers/menu.py`, `start.py`, `main.py` wiring

**Files:**
- Create: `bot/handlers/menu.py`
- Modify: `bot/handlers/start.py` (full-file rewrite)
- Modify: `bot/main.py`

**Interfaces:**
- Consumes: `complain.start_complaint_flow`, `complain.COMPLAIN_PROMPT` (Task 5); `status.build_status_text` (Task 3); `faq.FAQ_COMMON`, `faq.faq_keyboard` (Task 4); `admin.build_stats_text` (Task 6).
- Produces: `menu.main_menu_keyboard(is_admin: bool) -> InlineKeyboardMarkup`, `menu.router: Router`. Nothing later depends on these — this is the last task.

No automated tests for this task (handler layer).

- [ ] **Step 1: Create the menu module**

`bot/handlers/menu.py`:
```python
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.handlers import admin, complain, faq, status
from bot.marzban.client import MarzbanClient

router = Router(name="menu")


def main_menu_keyboard(is_admin: bool) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🔴 Сообщить о проблеме", callback_data="menu:complain")],
        [InlineKeyboardButton(text="📊 Мой статус", callback_data="menu:status")],
        [InlineKeyboardButton(text="📖 FAQ", callback_data="menu:faq")],
    ]
    if is_admin:
        buttons.append([InlineKeyboardButton(text="📈 Статистика", callback_data="menu:stats")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("menu"))
async def handle_menu_command(message: Message, admin_id: int) -> None:
    is_admin = message.from_user.id == admin_id
    await message.answer("Главное меню:", reply_markup=main_menu_keyboard(is_admin))


@router.callback_query(F.data == "menu:complain")
async def handle_menu_complain(callback: CallbackQuery, state: FSMContext) -> None:
    await complain.start_complaint_flow(state)
    await callback.message.answer(complain.COMPLAIN_PROMPT)
    await callback.answer()


@router.callback_query(F.data == "menu:status")
async def handle_menu_status(callback: CallbackQuery, conn, marzban: MarzbanClient) -> None:
    text = await status.build_status_text(conn, marzban, callback.from_user.id)
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "menu:faq")
async def handle_menu_faq(callback: CallbackQuery) -> None:
    await callback.message.answer(faq.FAQ_COMMON, reply_markup=faq.faq_keyboard())
    await callback.answer()


@router.callback_query(F.data == "menu:stats")
async def handle_menu_stats(callback: CallbackQuery, conn, admin_id: int) -> None:
    if callback.from_user.id != admin_id:
        await callback.answer()
        return
    text = await admin.build_stats_text(conn)
    await callback.message.answer(text)
    await callback.answer()
```

Note: `menu.py` imports `admin`, `complain`, `faq`, `status` from `bot.handlers`; none of those files import `menu` or `start`, so there is no circular import. `start.py` (Step 2 below) imports `main_menu_keyboard` from `menu.py`, which is safe for the same reason.

- [ ] **Step 2: Replace `bot/handlers/start.py`**

`bot/handlers/start.py`:
```python
from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message

from bot.db import link_tokens_repo, users_repo
from bot.handlers.menu import main_menu_keyboard

router = Router(name="start")

WELCOME_TEXT = (
    "Добро пожаловать! Доступные команды:\n"
    "🔴 /complain — сообщить о проблеме с VPN\n"
    "🌐 /status — статус вашего аккаунта\n"
    "📖 /faq — инструкции по подключению"
)


@router.message(CommandStart())
async def handle_start(message: Message, command: CommandObject, conn, admin_id: int) -> None:
    await users_repo.upsert_user(conn, message.from_user.id, message.from_user.username, message.from_user.first_name)
    is_admin = message.from_user.id == admin_id
    keyboard = main_menu_keyboard(is_admin)

    token = command.args
    if not token:
        await message.answer(WELCOME_TEXT, reply_markup=keyboard)
        return

    token_row = await link_tokens_repo.get_token(conn, token)
    if token_row is None or token_row["used_at"] is not None:
        await message.answer("⚠️ Эта ссылка недействительна или уже использована. Запросите новую у администратора.")
        return

    await users_repo.link_user(conn, message.from_user.id, token_row["marzban_login"])
    await link_tokens_repo.mark_used(conn, token, message.from_user.id)
    await message.answer(
        f"✅ Аккаунт привязан к логину {token_row['marzban_login']}. Теперь доступна команда /status.\n\n{WELCOME_TEXT}",
        reply_markup=keyboard,
    )
```

- [ ] **Step 3: Wire the menu router and `/menu` command into `bot/main.py`**

In `bot/main.py`:

1. Change the import line `from bot.handlers import admin, complain, faq, start, status` to:
```python
from bot.handlers import admin, complain, faq, menu, start, status
```

2. In `public_commands`, add `/menu` as the first entry:
```python
    public_commands = [
        BotCommand(command="menu", description="Главное меню"),
        BotCommand(command="complain", description="Сообщить о проблеме с VPN"),
        BotCommand(command="status", description="Статус вашего аккаунта"),
        BotCommand(command="faq", description="Инструкции по подключению"),
    ]
```

3. Add `dp.include_router(menu.router)` right after `dp.include_router(start.router)`:
```python
    dp.include_router(start.router)
    dp.include_router(menu.router)
    dp.include_router(complain.router)
    dp.include_router(status.router)
    dp.include_router(faq.router)
    dp.include_router(admin.create_admin_router(config.admin_id))
```

- [ ] **Step 4: Run the import sanity check**

Run: `python -c "import bot.main"`
Expected: exit code 0 (this specifically exercises the new import graph: `main -> start -> menu -> {admin, complain, faq, status}` — if there were a circular import it would fail here)

- [ ] **Step 5: Run the full suite to confirm no regressions**

Run: `pytest -q`
Expected: `44 passed` (unchanged — this task adds no automated tests)

- [ ] **Step 6: Commit**

```bash
git add bot/handlers/menu.py bot/handlers/start.py bot/main.py
git commit -m "feat: add inline main menu (buttons for complain/status/faq/stats)"
```

- [ ] **Step 7: Manual verification checklist (after deploying, with a real bot token/admin chat)**

1. `/start` from any account — welcome message now shows 3 buttons (4 for the admin account: + "📈 Статистика").
2. Tap "🔴 Сообщить о проблеме" — bot prompts for description (same as typing `/complain`); send text — confirmation with 🔴/✅ arrives, admin gets the forwarded complaint.
3. Tap "📊 Мой статус" — same output as `/status`, including the `[████░░░░░░] NN%` bar if the account has a data limit set in the panel.
4. Tap "📖 FAQ" — same platform-selection keyboard as `/faq`, now with emoji-prefixed platform names.
5. From the admin account, tap "📈 Статистика" — same output as `/stats`, ending with the 14-day `19.07 ████░░░░░░ 2` style chart.
6. Send `/menu` — re-shows the same button set without needing `/start` again.
7. From a non-admin account, confirm no "📈 Статистика" button appears, and that manually crafting the `menu:stats` callback (not really testable without a custom client — skip, the code-level admin check was covered in review) isn't something you need to test by hand.

---

## Self-Review Notes

- **Spec coverage:** main menu buttons → Task 7; emoji vocabulary → Tasks 3-6 (all handler text) + Task 7 (menu labels); complaint bar chart → Tasks 1 (render) + 2 (data) + 6 (wiring); usage bar → Tasks 1 (render) + 3 (wiring). All four spec sections covered.
- **Placeholder scan:** no TBD/TODO; every step has complete file contents or precise line-level instructions.
- **Type consistency:** `render_daily_bar_chart(counts_by_day: dict[str, int], days: int) -> str` and `render_usage_bar(used_bytes: int, limit_bytes: int | None, width: int = 10) -> str | None` are defined once (Task 1) and consumed with identical signatures in Tasks 3 and 6. `build_status_text`, `build_stats_text`, `start_complaint_flow`, `COMPLAIN_PROMPT`, `faq_keyboard`, `FAQ_COMMON` are each defined in exactly one task (3, 6, 5, 5, 4, 4 respectively) and consumed with matching names/signatures only in Task 7.
