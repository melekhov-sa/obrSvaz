from bot.db import reminders_repo, users_repo


async def test_was_sent_false_when_not_recorded(conn):
    assert await reminders_repo.was_sent(conn, 1, "2026-08-01") is False


async def test_mark_sent_then_was_sent_true(conn):
    await users_repo.upsert_user(conn, 1, "ivan", "Ivan")

    await reminders_repo.mark_sent(conn, 1, "2026-08-01")

    assert await reminders_repo.was_sent(conn, 1, "2026-08-01") is True


async def test_mark_sent_is_idempotent(conn):
    await users_repo.upsert_user(conn, 1, "ivan", "Ivan")

    await reminders_repo.mark_sent(conn, 1, "2026-08-01")
    await reminders_repo.mark_sent(conn, 1, "2026-08-01")

    assert await reminders_repo.was_sent(conn, 1, "2026-08-01") is True
