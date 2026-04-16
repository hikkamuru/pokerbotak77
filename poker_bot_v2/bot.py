from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

from app.database import get_or_create_player
from config.settings import settings

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await get_or_create_player(
        tg_id=message.from_user.id,
        username=message.from_user.username or "",
        full_name=message.from_user.full_name,
    )

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(
                text="🃏 Открыть приложение",
                web_app=WebAppInfo(url=settings.WEBAPP_URL),
            )]
        ],
        resize_keyboard=True,
    )

    await message.answer(
        f"👋 Привет, <b>{message.from_user.first_name}</b>!\n\n"
        f"Добро пожаловать в <b>{settings.CLUB_NAME}</b>.\n\n"
        f"Нажми кнопку ниже, чтобы открыть приложение 👇",
        reply_markup=keyboard,
    )
