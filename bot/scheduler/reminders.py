from datetime import datetime, timezone

from bot.db import reminders_repo, users_repo
from bot.marzban.status import UserStatus


async def check_and_send_reminders(conn, marzban, bot, reminder_days: int, now_timestamp: int | None = None) -> int:
    if now_timestamp is None:
        now_timestamp = int(datetime.now(timezone.utc).timestamp())

    sent_count = 0
    linked_users = await users_repo.get_linked_users(conn)
    for user in linked_users:
        data = await marzban.get_user(user["marzban_login"])
        if data is None:
            continue
        status = UserStatus.from_api(user["marzban_login"], data)
        days_left = status.days_until_expiry(now_timestamp)
        if days_left is None or days_left > reminder_days or days_left < 0:
            continue
        sent_for_date = str(status.expire_timestamp)
        if await reminders_repo.was_sent(conn, user["telegram_id"], sent_for_date):
            continue
        await bot.send_message(
            user["telegram_id"],
            f"Напоминаем: ваша подписка истекает через {days_left} дн. Продлите доступ у администратора.",
        )
        await reminders_repo.mark_sent(conn, user["telegram_id"], sent_for_date)
        sent_count += 1
    return sent_count
