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
