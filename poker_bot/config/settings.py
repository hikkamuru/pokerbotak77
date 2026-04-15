from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    BOT_TOKEN: str
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

    @property
    def admin_list(self) -> list[int]:
        return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip()]


settings = Settings()
