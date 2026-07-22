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
