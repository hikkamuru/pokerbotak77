from pydantic_settings import BaseSettings
from pydantic import model_validator


class Settings(BaseSettings):
    BOT_TOKEN: str = ""
    TOKEN: str = ""               # bothost.ru passes token as TOKEN
    TELEGRAM_BOT_TOKEN: str = ""  # bothost.ru also sets this
    ADMIN_IDS: str = ""
    CLUB_NAME: str = "Poker Club"
    WEBAPP_URL: str = "https://ak-77-poker.ru/"
    WEBAPP_HOST: str = "0.0.0.0"
    WEBAPP_PORT: int = 8080

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @model_validator(mode="after")
    def resolve_token(self) -> "Settings":
        if not self.BOT_TOKEN:
            self.BOT_TOKEN = self.TOKEN or self.TELEGRAM_BOT_TOKEN
        if not self.BOT_TOKEN:
            raise ValueError(
                "Bot token not found. Set BOT_TOKEN (or TOKEN / TELEGRAM_BOT_TOKEN)."
            )
        return self

    @property
    def admin_list(self) -> list[int]:
        return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip()]


settings = Settings()
