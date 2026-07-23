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
