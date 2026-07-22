from bot.db import link_tokens_repo


def test_generate_token_has_expected_format():
    token = link_tokens_repo.generate_token()

    assert token.startswith("LNK_")
    assert len(token) == len("LNK_") + 8


async def test_create_token_persists_and_is_retrievable(conn):
    token = await link_tokens_repo.create_token(conn, "ivan_login")

    row = await link_tokens_repo.get_token(conn, token)

    assert row["marzban_login"] == "ivan_login"
    assert row["used_at"] is None


async def test_get_token_returns_none_for_unknown_token(conn):
    row = await link_tokens_repo.get_token(conn, "LNK_UNKNOWN")
    assert row is None


async def test_mark_used_sets_used_fields(conn):
    token = await link_tokens_repo.create_token(conn, "ivan_login")

    await link_tokens_repo.mark_used(conn, token, telegram_id=42)

    row = await link_tokens_repo.get_token(conn, token)
    assert row["used_at"] is not None
    assert row["used_by"] == 42
