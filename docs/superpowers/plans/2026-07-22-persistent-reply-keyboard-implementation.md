# Persistent Reply Keyboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the message-attached inline-button main menu with a persistent reply-keyboard (bottom button panel) that stays current across the whole chat, fixing the stale-old-message problem, and close a related pre-existing gap where navigating away mid-complaint didn't clear the FSM state.

**Architecture:** Single-file rewrite of `bot/handlers/menu.py`. `bot/handlers/start.py` and `bot/main.py` need zero changes — they pass `main_menu_keyboard(...)`'s return value straight into `reply_markup=`, and aiogram accepts any keyboard type there.

**Tech Stack:** Same as the deployed project — Python 3.12, aiogram 3. No new dependencies.

## Global Constraints

- `main_menu_keyboard(is_admin: bool)` keeps its exact name and boolean parameter — only its return type changes (`ReplyKeyboardMarkup` instead of `InlineKeyboardMarkup`) and only inside `menu.py`. No caller outside this file changes.
- Button set unchanged: 🔴 Сообщить о проблеме, 📊 Мой статус, 📖 FAQ always; 📈 Статистика only when `is_admin` is True.
- `handle_menu_stats`'s admin gate (`message.from_user.id != admin_id` → refuse) must be preserved — this is the same security-critical check from the previous plan, just on a `Message` handler instead of a `CallbackQuery` handler now.
- `handle_menu_status`, `handle_menu_faq`, `handle_menu_stats` must call `await state.clear()` before doing their own work, so tapping a menu button always cancels any in-progress `/complain` flow. `handle_menu_complain` does NOT need this — it immediately calls `start_complaint_flow(state)`, which sets the state to the same value regardless of what it was before.
- FAQ's platform-selection keyboard (`faq.faq_keyboard()`) stays an inline keyboard, unchanged — this plan doesn't touch `bot/handlers/faq.py`.
- No automated tests for this task (handler layer) — established project policy.

---

### Task 1: Rewrite `bot/handlers/menu.py` for a persistent reply keyboard

**Files:**
- Modify: `bot/handlers/menu.py` (full-file rewrite)

**Interfaces:**
- Consumes: `complain.start_complaint_flow`, `complain.COMPLAIN_PROMPT`, `status.build_status_text`, `faq.FAQ_COMMON`, `faq.faq_keyboard`, `admin.build_stats_text` — all already exist and unchanged, from the previous plan.
- Produces: `main_menu_keyboard(is_admin: bool) -> ReplyKeyboardMarkup`, `router: Router`. Same names as before; `bot/handlers/start.py` and `bot/main.py` keep working unmodified since they only reference these two names generically.

No automated tests for this task (handler layer — see Global Constraints).

- [ ] **Step 1: Replace the entire file**

`bot/handlers/menu.py`:
```python
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

from bot.handlers import admin, complain, faq, status
from bot.marzban.client import MarzbanClient

router = Router(name="menu")

BUTTON_COMPLAIN = "🔴 Сообщить о проблеме"
BUTTON_STATUS = "📊 Мой статус"
BUTTON_FAQ = "📖 FAQ"
BUTTON_STATS = "📈 Статистика"


def main_menu_keyboard(is_admin: bool) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text=BUTTON_COMPLAIN)],
        [KeyboardButton(text=BUTTON_STATUS)],
        [KeyboardButton(text=BUTTON_FAQ)],
    ]
    if is_admin:
        buttons.append([KeyboardButton(text=BUTTON_STATS)])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


@router.message(Command("menu"))
async def handle_menu_command(message: Message, admin_id: int) -> None:
    is_admin = message.from_user.id == admin_id
    await message.answer("Главное меню:", reply_markup=main_menu_keyboard(is_admin))


@router.message(F.text == BUTTON_COMPLAIN)
async def handle_menu_complain(message: Message, state: FSMContext) -> None:
    await complain.start_complaint_flow(state)
    await message.answer(complain.COMPLAIN_PROMPT)


@router.message(F.text == BUTTON_STATUS)
async def handle_menu_status(message: Message, state: FSMContext, conn, marzban: MarzbanClient) -> None:
    await state.clear()
    text = await status.build_status_text(conn, marzban, message.from_user.id)
    await message.answer(text)


@router.message(F.text == BUTTON_FAQ)
async def handle_menu_faq(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(faq.FAQ_COMMON, reply_markup=faq.faq_keyboard())


@router.message(F.text == BUTTON_STATS)
async def handle_menu_stats(message: Message, state: FSMContext, conn, admin_id: int) -> None:
    if message.from_user.id != admin_id:
        return
    await state.clear()
    text = await admin.build_stats_text(conn)
    await message.answer(text)
```

Note on handler ordering: these `F.text == "..."` handlers have no FSM-state filter (unlike `complain.py`'s `handle_complain_text`, which is scoped to `ComplainStates.waiting_for_text`). `menu.router` is registered before `complain.router` in `bot/main.py`, so if a user is mid-complaint and sends text that happens to exactly match a menu button's label, the menu handler wins and (per the `state.clear()` calls above) cleanly cancels the complaint — this is the intended behavior described in the design spec, not a bug to fix here.

- [ ] **Step 2: Run the import sanity check**

Run: `python -c "import bot.main"` (or `py -3.13 -c "import bot.main"` — use whatever invocation has worked in this environment)
Expected: exit code 0

- [ ] **Step 3: Run the full suite to confirm no regressions**

Run: `pytest -q`
Expected: `44 passed` (unchanged — this task adds no tests, matches the count from the end of the previous plan)

- [ ] **Step 4: Commit**

```bash
git add bot/handlers/menu.py
git commit -m "feat: switch main menu from inline buttons to a persistent reply keyboard"
```

- [ ] **Step 5: Manual verification checklist (after deploying, with a real bot token/admin chat)**

1. Send `/start` — a keyboard panel appears below the text input (not attached to the message bubble itself).
2. Send any other unrelated text — the keyboard panel stays visible (this is the behavior that was broken with inline buttons).
3. From the admin account, count the buttons — 4, including "📈 Статистика". From a non-admin account — 3.
4. Tap "🔴 Сообщить о проблеме", then instead of describing a problem, tap "📊 Мой статус" — should show status immediately, NOT record "📊 Мой статус" as complaint text (confirms the `state.clear()` fix).
5. Tap each button once and confirm the output matches the equivalent slash command (`/complain`, `/status`, `/faq`, `/stats` for admin).

---

## Self-Review Notes

- **Spec coverage:** reply-keyboard swap → Step 1; FSM-clear-on-navigation fix → Step 1 (three `state.clear()` calls); FAQ inline picker left untouched → confirmed, this task doesn't touch `faq.py`. All spec sections covered in this single task.
- **Placeholder scan:** none.
- **Type consistency:** `main_menu_keyboard(is_admin: bool) -> ReplyKeyboardMarkup` is the only interface anything outside this file depends on, and its name/parameter are unchanged from the previous plan, so `start.py`/`main.py` need no corresponding updates — verified by reading their current content, neither references `ReplyKeyboardMarkup`/`InlineKeyboardMarkup` by name, only the generic `reply_markup=main_menu_keyboard(is_admin)` / `menu.router`.
