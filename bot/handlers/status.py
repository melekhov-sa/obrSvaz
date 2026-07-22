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
