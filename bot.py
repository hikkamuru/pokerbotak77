from urllib.parse import quote
import logging

from aiogram import Router, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from app.database import get_or_create_player, update_photo_url
from config.settings import settings

router = Router()
_log = logging.getLogger(__name__)


async def _save_profile_photo(bot: Bot, tg_id: int) -> None:
    """Fetch the user's current profile photo via Bot API and store in DB."""
    try:
        photos = await bot.get_user_profile_photos(tg_id, limit=1)
        if photos.total_count == 0:
            return
        file_id = photos.photos[0][-1].file_id  # largest size
        file = await bot.get_file(file_id)
        token = settings.BOT_TOKEN
        url = f"https://api.telegram.org/file/bot{token}/{file.file_path}"
        await update_photo_url(tg_id, url)
    except Exception as e:
        _log.warning("[photo] failed for tg_id=%s: %s", tg_id, e)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    tg_name = (
        (message.from_user.first_name or "") + " " +
        (message.from_user.last_name or "")
    ).strip()
    await get_or_create_player(
        tg_id=message.from_user.id,
        username=message.from_user.username or "",
        tg_name=tg_name,
    )

    # Save profile photo in background (non-blocking)
    await _save_profile_photo(message.bot, message.from_user.id)

    # Embed user identity in the URL — works even when Telegram Desktop
    # or some mobile clients don't populate initData / initDataUnsafe.
    base = settings.WEBAPP_URL.rstrip("/")
    fn   = quote(message.from_user.first_name or "", safe="")
    un   = quote(message.from_user.username   or "", safe="")
    webapp_url = f"{base}?tg={message.from_user.id}&fn={fn}&un={un}"

    # InlineKeyboardMarkup — button is attached to the message permanently
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🃏 Открыть клуб AK77",
                web_app=WebAppInfo(url=webapp_url),
            )]
        ]
    )

    await message.answer(
        f"Привет, <b>{message.from_user.first_name}</b>! 👋\n\n"
        f"Добро пожаловать в <b>{settings.CLUB_NAME}</b> — покерный клуб для своих.\n\n"
        f"Нажми кнопку ниже, чтобы открыть приложение клуба 👇",
        reply_markup=keyboard,
    )
