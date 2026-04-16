import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
    ADMIN_IDS: list = None
    DB_PATH: str = os.getenv("DB_PATH", "poker_bot.db")
    WEBAPP_URL: str = os.getenv("WEBAPP_URL", "http://localhost:8080")
    WEBAPP_HOST: str = os.getenv("WEBAPP_HOST", "0.0.0.0")
    WEBAPP_PORT: int = int(os.getenv("WEBAPP_PORT", "8080"))
    WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")
    WEBHOOK_PATH: str = "/webhook"

    # Название клуба
    CLUB_NAME: str = os.getenv("CLUB_NAME", "Poker Club")
    CLUB_CITY: str = os.getenv("CLUB_CITY", "Москва")
    CLUB_ADDRESS: str = os.getenv("CLUB_ADDRESS", "ул. Примерная, 1")

    def __post_init__(self):
        if self.ADMIN_IDS is None:
            raw = os.getenv("ADMIN_IDS", "")
            self.ADMIN_IDS = [int(x) for x in raw.split(",") if x.strip()]


config = Config()
