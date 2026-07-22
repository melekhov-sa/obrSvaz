import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    bot_token: str
    admin_id: int
    marzban_url: str
    marzban_username: str
    marzban_password: str
    reminder_days: int
    db_path: str


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_config() -> Config:
    return Config(
        bot_token=_require("BOT_TOKEN"),
        admin_id=int(_require("ADMIN_ID")),
        marzban_url=_require("MARZBAN_URL"),
        marzban_username=_require("MARZBAN_USERNAME"),
        marzban_password=_require("MARZBAN_PASSWORD"),
        reminder_days=int(os.getenv("REMINDER_DAYS", "3")),
        db_path=os.getenv("DB_PATH", "bot.db"),
    )
