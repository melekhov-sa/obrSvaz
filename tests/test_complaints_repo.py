from datetime import datetime, timedelta, timezone

from bot.db import complaints_repo, users_repo


async def test_add_complaint_returns_id(conn):
    await users_repo.upsert_user(conn, 1, "ivan", "Ivan")

    complaint_id = await complaints_repo.add_complaint(conn, 1, "Не работает интернет")

    assert complaint_id == 1


async def test_count_all(conn):
    await users_repo.upsert_user(conn, 1, "ivan", "Ivan")
    await complaints_repo.add_complaint(conn, 1, "Проблема 1")
    await complaints_repo.add_complaint(conn, 1, "Проблема 2")

    assert await complaints_repo.count_all(conn) == 2


async def test_count_since_filters_by_date(conn):
    await users_repo.upsert_user(conn, 1, "ivan", "Ivan")
    await complaints_repo.add_complaint(conn, 1, "Свежая жалоба")

    future_cutoff = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    past_cutoff = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    assert await complaints_repo.count_since(conn, past_cutoff) == 1
    assert await complaints_repo.count_since(conn, future_cutoff) == 0


async def test_count_by_user_groups_correctly(conn):
    await users_repo.upsert_user(conn, 1, "ivan", "Ivan")
    await users_repo.upsert_user(conn, 2, "petr", "Petr")
    await complaints_repo.add_complaint(conn, 1, "a")
    await complaints_repo.add_complaint(conn, 1, "b")
    await complaints_repo.add_complaint(conn, 2, "c")

    counts = await complaints_repo.count_by_user(conn)
    counts_by_id = {row[0]: row[1] for row in counts}

    assert counts_by_id[1] == 2
    assert counts_by_id[2] == 1
