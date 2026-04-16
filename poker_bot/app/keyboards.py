from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from config.settings import settings


def main_menu_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(
        text="🃏 Открыть приложение",
        web_app=WebAppInfo(url=settings.WEBAPP_URL)
    )
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True)


def tournaments_list_kb(tournaments: list, player_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for t in tournaments:
        filled = t.get("registered_count", 0)
        total = t.get("max_players", 100)
        kb.button(
            text=f"🎯 {t['title']}  •  {filled}/{total}",
            callback_data=f"tour:{t['id']}"
        )
    kb.adjust(1)
    return kb.as_markup()


def tournament_detail_kb(tournament_id: int, is_registered: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if is_registered:
        kb.button(text="❌ Отменить регистрацию", callback_data=f"unreg:{tournament_id}")
    else:
        kb.button(text="✅ Зарегистрироваться", callback_data=f"reg:{tournament_id}")
    kb.button(text="👥 Участники", callback_data=f"participants:{tournament_id}")
    kb.button(text="◀️ Назад", callback_data="back_tournaments")
    kb.adjust(1)
    return kb.as_markup()


def booking_time_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    slots = ["18:00", "19:00", "20:00", "21:00", "22:00"]
    for slot in slots:
        kb.button(text=slot, callback_data=f"slot:{slot}")
    kb.button(text="◀️ Отмена", callback_data="cancel_booking")
    kb.adjust(3, 2, 1)
    return kb.as_markup()


def booking_seats_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for i in range(1, 7):
        kb.button(text=str(i), callback_data=f"seats:{i}")
    kb.button(text="◀️ Отмена", callback_data="cancel_booking")
    kb.adjust(3, 3, 1)
    return kb.as_markup()


def confirm_booking_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить", callback_data="confirm_booking")
    kb.button(text="❌ Отмена", callback_data="cancel_booking")
    kb.adjust(2)
    return kb.as_markup()


def admin_booking_kb(booking_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Одобрить", callback_data=f"admin_book_ok:{booking_id}")
    kb.button(text="❌ Отклонить", callback_data=f"admin_book_no:{booking_id}")
    kb.adjust(2)
    return kb.as_markup()


def admin_panel_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Создать турнир",     callback_data="adm:new_tour")
    kb.button(text="📋 Заявки на бронь",    callback_data="adm:bookings")
    kb.button(text="🏁 Завершить турнир",   callback_data="adm:finish_tour")
    kb.button(text="📊 Экспорт рейтинга",   callback_data="adm:export")
    kb.button(text="📣 Рассылка",           callback_data="adm:broadcast")
    kb.button(text="📈 Статистика клуба",   callback_data="adm:stats")
    kb.adjust(1)
    return kb.as_markup()


def back_kb(callback: str = "back_main") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ Назад", callback_data=callback)
    return kb.as_markup()
