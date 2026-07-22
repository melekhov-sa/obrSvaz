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
