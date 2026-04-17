import subprocess
import sys

# Install missing packages at runtime (for bothost.ru)
subprocess.check_call([
    sys.executable, "-m", "pip", "install", "--quiet",
    "aiosqlite==0.20.0", "pydantic-settings==2.7.0"
])

import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from app.database import init_db
from config.settings import settings


async def main() -> None:
    await init_db()

    from aiogram import Bot, Dispatcher
    from aiogram.enums import ParseMode
    from aiogram.client.default import DefaultBotProperties
    from aiogram.fsm.storage.memory import MemoryStorage
    from mini_app.server import run_webapp
    import bot as bot_module

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(bot_module.router)

    webapp_runner = await run_webapp()

    logging.info(f"Bot started. Mini App: {settings.WEBAPP_URL}")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await webapp_runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
