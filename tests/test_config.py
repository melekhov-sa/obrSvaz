import pytest

from bot.config import load_config


def test_load_config_reads_required_and_defaults(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "test-token")
    monkeypatch.setenv("ADMIN_ID", "12345")
    monkeypatch.setenv("MARZBAN_URL", "https://panel.example.com")
    monkeypatch.setenv("MARZBAN_USERNAME", "admin")
    monkeypatch.setenv("MARZBAN_PASSWORD", "secret")
    monkeypatch.delenv("REMINDER_DAYS", raising=False)
    monkeypatch.delenv("DB_PATH", raising=False)

    config = load_config()

    assert config.bot_token == "test-token"
    assert config.admin_id == 12345
    assert config.marzban_url == "https://panel.example.com"
    assert config.reminder_days == 3
    assert config.db_path == "bot.db"


def test_load_config_raises_when_required_missing(monkeypatch):
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("ADMIN_ID", raising=False)
    monkeypatch.delenv("MARZBAN_URL", raising=False)
    monkeypatch.delenv("MARZBAN_USERNAME", raising=False)
    monkeypatch.delenv("MARZBAN_PASSWORD", raising=False)

    with pytest.raises(RuntimeError):
        load_config()
