from bot.db import reminders_repo, users_repo
from bot.scheduler.reminders import check_and_send_reminders

NOW = 1_700_000_000
DAY = 86400


class FakeBot:
    def __init__(self):
        self.sent_messages = []

    async def send_message(self, chat_id, text):
        self.sent_messages.append((chat_id, text))


class FakeMarzban:
    def __init__(self, users):
        self._users = users

    async def get_user(self, login):
        return self._users.get(login)


async def _linked_user(conn, telegram_id, login):
    await users_repo.upsert_user(conn, telegram_id, "user", "User")
    await users_repo.link_user(conn, telegram_id, login)


async def test_sends_reminder_within_threshold(conn):
    await _linked_user(conn, 1, "ivan")
    marzban = FakeMarzban({"ivan": {"status": "active", "used_traffic": 0, "data_limit": None, "expire": NOW + 2 * DAY}})
    bot = FakeBot()

    sent = await check_and_send_reminders(conn, marzban, bot, reminder_days=3, now_timestamp=NOW)

    assert sent == 1
    assert bot.sent_messages[0][0] == 1
    assert await reminders_repo.was_sent(conn, 1, str(NOW + 2 * DAY))


async def test_skips_beyond_threshold(conn):
    await _linked_user(conn, 1, "ivan")
    marzban = FakeMarzban({"ivan": {"status": "active", "used_traffic": 0, "data_limit": None, "expire": NOW + 10 * DAY}})
    bot = FakeBot()

    sent = await check_and_send_reminders(conn, marzban, bot, reminder_days=3, now_timestamp=NOW)

    assert sent == 0
    assert bot.sent_messages == []


async def test_does_not_resend_same_reminder(conn):
    await _linked_user(conn, 1, "ivan")
    marzban = FakeMarzban({"ivan": {"status": "active", "used_traffic": 0, "data_limit": None, "expire": NOW + 2 * DAY}})
    bot = FakeBot()

    await check_and_send_reminders(conn, marzban, bot, reminder_days=3, now_timestamp=NOW)
    sent_second_run = await check_and_send_reminders(conn, marzban, bot, reminder_days=3, now_timestamp=NOW)

    assert sent_second_run == 0
    assert len(bot.sent_messages) == 1


async def test_skips_users_without_expiry(conn):
    await _linked_user(conn, 1, "ivan")
    marzban = FakeMarzban({"ivan": {"status": "active", "used_traffic": 0, "data_limit": None, "expire": None}})
    bot = FakeBot()

    sent = await check_and_send_reminders(conn, marzban, bot, reminder_days=3, now_timestamp=NOW)

    assert sent == 0


async def test_skips_unlinked_users(conn):
    await users_repo.upsert_user(conn, 1, "user", "User")
    marzban = FakeMarzban({})
    bot = FakeBot()

    sent = await check_and_send_reminders(conn, marzban, bot, reminder_days=3, now_timestamp=NOW)

    assert sent == 0
    assert bot.sent_messages == []
