from datetime import datetime, timedelta, timezone

from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from bot.db import complaints_repo, link_tokens_repo, users_repo
from bot.filters import IsAdmin


def create_admin_router(admin_id: int) -> Router:
    router = Router(name="admin")
    router.message.filter(IsAdmin(admin_id))

    @router.message(Command("genlink"))
    async def handle_genlink(message: Message, command: CommandObject, conn) -> None:
        login = (command.args or "").strip()
        if not login:
            await message.answer("Использование: /genlink <логин_в_панели>")
            return
        token = await link_tokens_repo.create_token(conn, login)
        bot_username = (await message.bot.get_me()).username
        await message.answer(f"Ссылка для {login}:\nhttps://t.me/{bot_username}?start={token}")

    @router.message(Command("broadcast"))
    async def handle_broadcast(message: Message, command: CommandObject, conn, bot: Bot) -> None:
        text = command.args
        if not text:
            await message.answer("Использование: /broadcast <текст сообщения>")
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

        await message.answer(f"Рассылка завершена. Доставлено: {delivered}, не доставлено: {failed}")

    @router.message(Command("stats"))
    async def handle_stats(message: Message, conn) -> None:
        total = await complaints_repo.count_all(conn)
        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        last_week = await complaints_repo.count_since(conn, week_ago)
        by_user = await complaints_repo.count_by_user(conn)

        lines = [f"Всего жалоб: {total}", f"За последние 7 дней: {last_week}", "", "По пользователям:"]
        for row in by_user:
            lines.append(f"  {row['telegram_id']}: {row['cnt']}")

        await message.answer("\n".join(lines))

    return router
