from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.keyboards import main_menu_kb
from config.settings import settings

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, player: dict):
    name = player["full_name"].split()[0]
    await message.answer(
        f"👋 Привет, <b>{name}</b>!\n\n"
        f"Добро пожаловать в <b>{settings.CLUB_NAME}</b> — покерный клуб.\n\n"
        f"Открой приложение, чтобы:\n"
        f"• 🏆 Записаться на турниры\n"
        f"• 📅 Забронировать стол\n"
        f"• ⭐ Смотреть рейтинг игроков\n"
        f"• 👤 Управлять профилем\n\n"
        f"Нажми кнопку ниже 👇",
        reply_markup=main_menu_kb()
    )
