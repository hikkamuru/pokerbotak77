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
    from mini_app.server import create_app
    import bot as bot_module
    from aiohttp import web

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(bot_module.router)

    # Delete any existing webhook so polling works cleanly
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("[Bot] webhook deleted, starting polling")

    # Start web app
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.WEBAPP_HOST, settings.WEBAPP_PORT)
    await site.start()
    logging.info(f"[Server] running on :{settings.WEBAPP_PORT}")

    # Start polling
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
