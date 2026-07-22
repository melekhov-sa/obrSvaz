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
