import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.config import load_config
from bot.db.database import open_db
from bot.handlers import admin, complain, faq, start, status
from bot.marzban.client import MarzbanClient
from bot.scheduler.reminders import check_and_send_reminders

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    config = load_config()
    conn = await open_db(config.db_path)
    marzban = MarzbanClient(config.marzban_url, config.marzban_username, config.marzban_password)

    bot = Bot(token=config.bot_token)

    public_commands = [
        BotCommand(command="complain", description="Сообщить о проблеме с VPN"),
        BotCommand(command="status", description="Статус вашего аккаунта"),
        BotCommand(command="faq", description="Инструкции по подключению"),
    ]
    admin_commands = public_commands + [
        BotCommand(command="genlink", description="Сгенерировать ссылку для привязки"),
        BotCommand(command="unlink", description="Снять привязку пользователя"),
        BotCommand(command="broadcast", description="Разослать сообщение всем"),
        BotCommand(command="stats", description="Статистика"),
    ]
    try:
        await bot.set_my_commands(public_commands, scope=BotCommandScopeDefault())
        await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=config.admin_id))
    except Exception:
        logger.exception("Failed to register bot command menus; continuing without them")

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(start.router)
    dp.include_router(complain.router)
    dp.include_router(status.router)
    dp.include_router(faq.router)
    dp.include_router(admin.create_admin_router(config.admin_id))

    scheduler = AsyncIOScheduler()

    async def reminders_job() -> None:
        try:
            sent = await check_and_send_reminders(conn, marzban, bot, config.reminder_days)
            logger.info("Reminder job sent %d reminders", sent)
        except Exception:
            logger.exception("Reminder job failed")

    scheduler.add_job(reminders_job, "cron", hour=10, minute=0)
    scheduler.start()

    try:
        await dp.start_polling(bot, conn=conn, marzban=marzban, admin_id=config.admin_id)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
