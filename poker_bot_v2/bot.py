from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

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

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(
                text="🃏 Открыть клуб AK77",
                web_app=WebAppInfo(url=settings.WEBAPP_URL),
            )]
        ],
        resize_keyboard=True,
    )

    await message.answer(
        f"Привет, <b>{message.from_user.first_name}</b>! 👋\n\n"
        f"Добро пожаловать в <b>{settings.CLUB_NAME}</b> — покерный клуб для своих.\n\n"
        f"Нажми кнопку ниже, чтобы открыть приложение клуба 👇",
        reply_markup=keyboard,
    )
