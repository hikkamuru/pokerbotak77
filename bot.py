from urllib.parse import quote

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from app.database import get_or_create_player
from config.settings import settings

router = Router()


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
