from pydantic_settings import BaseSettings
from pydantic import model_validator
from pathlib import Path
import os


class Settings(BaseSettings):
    BOT_TOKEN: str = ""
    TOKEN: str = ""              # bothost.ru passes token as TOKEN
    TELEGRAM_BOT_TOKEN: str = "" # bothost.ru also sets this
    ADMIN_IDS: str = ""          # comma-separated Telegram IDs
    CLUB_NAME: str = "Poker Club"
    CLUB_CITY: str = "Москва"
    CLUB_ADDRESS: str = "ул. Примерная, 1"
    WEBAPP_URL: str = "http://localhost:8080"   # public URL of the Mini App (static host)
    API_URL: str = ""                           # public URL of the Python server (e.g. https://my-app.railway.app)
    WEBAPP_HOST: str = "0.0.0.0"
    WEBHOOK_URL: str = ""        # leave empty to use polling
    WEBHOOK_PORT: int = 8443
    WEBAPP_PORT: int = 8080
    DB_PATH: str = "poker_bot.db"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @model_validator(mode="after")
    def resolve_token(self) -> "Settings":
        """Accept BOT_TOKEN, TOKEN or TELEGRAM_BOT_TOKEN — whichever is set."""
        if not self.BOT_TOKEN:
            self.BOT_TOKEN = self.TOKEN or self.TELEGRAM_BOT_TOKEN
        if not self.BOT_TOKEN:
            raise ValueError(
                "Bot token not found. Set BOT_TOKEN (or TOKEN / TELEGRAM_BOT_TOKEN) env variable."
            )
        return self

    @property
    def admin_list(self) -> list[int]:
        return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip()]


settings = Settings()
