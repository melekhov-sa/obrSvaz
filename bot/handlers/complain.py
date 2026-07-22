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
