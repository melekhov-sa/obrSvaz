from bot.db import users_repo


async def test_upsert_creates_new_user(conn):
    await users_repo.upsert_user(conn, 1, "ivan", "Ivan")

    user = await users_repo.get_user(conn, 1)

    assert user["telegram_id"] == 1
    assert user["username"] == "ivan"
    assert user["marzban_login"] is None


async def test_upsert_updates_existing_user(conn):
    await users_repo.upsert_user(conn, 1, "ivan", "Ivan")
    await users_repo.upsert_user(conn, 1, "ivan_new", "Ivan")

    user = await users_repo.get_user(conn, 1)

    assert user["username"] == "ivan_new"


async def test_get_user_returns_none_when_missing(conn):
    user = await users_repo.get_user(conn, 999)
    assert user is None


async def test_link_user_sets_marzban_login(conn):
    await users_repo.upsert_user(conn, 1, "ivan", "Ivan")

    await users_repo.link_user(conn, 1, "ivan_login")

    user = await users_repo.get_user(conn, 1)
    assert user["marzban_login"] == "ivan_login"
    assert user["linked_at"] is not None


async def test_link_user_reassigns_from_previous_owner(conn):
    await users_repo.upsert_user(conn, 1, "ivan", "Ivan")
    await users_repo.upsert_user(conn, 2, "petr", "Petr")
    await users_repo.link_user(conn, 1, "shared_login")

    await users_repo.link_user(conn, 2, "shared_login")

    old_owner = await users_repo.get_user(conn, 1)
    new_owner = await users_repo.get_user(conn, 2)
    assert old_owner["marzban_login"] is None
    assert new_owner["marzban_login"] == "shared_login"


async def test_get_linked_users_returns_only_linked(conn):
    await users_repo.upsert_user(conn, 1, "ivan", "Ivan")
    await users_repo.upsert_user(conn, 2, "petr", "Petr")
    await users_repo.link_user(conn, 1, "ivan_login")

    linked = await users_repo.get_linked_users(conn)

    assert len(linked) == 1
    assert linked[0]["telegram_id"] == 1


async def test_get_all_users_returns_everyone(conn):
    await users_repo.upsert_user(conn, 1, "ivan", "Ivan")
    await users_repo.upsert_user(conn, 2, "petr", "Petr")

    all_users = await users_repo.get_all_users(conn)

    assert len(all_users) == 2


async def test_unlink_by_login_clears_fields_and_returns_row(conn):
    await users_repo.upsert_user(conn, 1, "ivan", "Ivan")
    await users_repo.link_user(conn, 1, "ivan_login")

    row = await users_repo.unlink_by_login(conn, "ivan_login")

    assert row["telegram_id"] == 1
    user = await users_repo.get_user(conn, 1)
    assert user["marzban_login"] is None
    assert user["linked_at"] is None


async def test_unlink_by_login_returns_none_when_not_found(conn):
    row = await users_repo.unlink_by_login(conn, "nonexistent_login")
    assert row is None


async def test_unlink_by_login_does_not_affect_other_users(conn):
    await users_repo.upsert_user(conn, 1, "ivan", "Ivan")
    await users_repo.upsert_user(conn, 2, "petr", "Petr")
    await users_repo.link_user(conn, 1, "ivan_login")
    await users_repo.link_user(conn, 2, "petr_login")

    await users_repo.unlink_by_login(conn, "ivan_login")

    petr = await users_repo.get_user(conn, 2)
    assert petr["marzban_login"] == "petr_login"
