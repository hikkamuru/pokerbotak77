import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from app.database import init_db
from config.settings import settings

WEBHOOK_PATH = "/tg-webhook"


async def main() -> None:
    await init_db()

    from aiogram import Bot, Dispatcher
    from aiogram.enums import ParseMode
    from aiogram.client.default import DefaultBotProperties
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
    from mini_app.server import create_app
    import bot as bot_module
    from aiohttp import web

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(bot_module.router)

    # ── Webhook mode ──────────────────────────────────────────────────────────
    # Setting a webhook automatically kills any competing polling bots
    # (bothost.ru etc) — Telegram will reject their getUpdates requests.
    webhook_url = settings.WEBAPP_URL.rstrip("/") + WEBHOOK_PATH
    await bot.set_webhook(
        url=webhook_url,
        drop_pending_updates=True,   # discard stale updates from old bot
        allowed_updates=["message", "callback_query", "inline_query"],
    )
    logging.info(f"[Webhook] set to {webhook_url}")

    # ── Web app ───────────────────────────────────────────────────────────────
    app = create_app()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.WEBAPP_HOST, settings.WEBAPP_PORT)
    await site.start()

    logging.info(f"[Server] running on :{settings.WEBAPP_PORT}  webapp={settings.WEBAPP_URL}")

    # Run until killed
    try:
        await asyncio.Event().wait()
    finally:
        await bot.delete_webhook()
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
