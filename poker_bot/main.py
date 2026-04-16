"""
Entry point: runs the Telegram bot and Mini App web server concurrently.
"""
import subprocess, sys

# bothost.ru does not use our Dockerfile — install missing packages at runtime
subprocess.check_call([
    sys.executable, "-m", "pip", "install", "--quiet",
    "aiosqlite==0.20.0", "pydantic-settings==2.7.0"
])

import asyncio
import logging

from app.database import init_db
from config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)


async def main():
    await init_db()

    from aiogram import Bot, Dispatcher
    from aiogram.enums import ParseMode
    from aiogram.client.default import DefaultBotProperties
    from aiogram.fsm.storage.memory import MemoryStorage
    from app.handlers import start, tournament, booking, profile, admin
    from app.middlewares.auth import AuthMiddleware
    from mini_app.server import run_webapp

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    dp.include_router(start.router)
    dp.include_router(tournament.router)
    dp.include_router(booking.router)
    dp.include_router(profile.router)
    dp.include_router(admin.router)

    webapp_runner = await run_webapp()

    from app.services.notifications import notification_loop

    logging.info(f"Bot started. Mini App: {settings.WEBAPP_URL}")
    try:
        await asyncio.gather(
            dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types()),
            notification_loop(bot),
        )
    finally:
        await webapp_runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
