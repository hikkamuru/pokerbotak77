from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
)
from config import config


def main_menu_keyboard(webapp_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🃏 Открыть приложение",
            web_app=WebAppInfo(url=webapp_url)
        )],
        [InlineKeyboardButton(text="🏆 Турниры", callback_data="tournaments"),
         InlineKeyboardButton(text="⭐ Рейтинг", callback_data="rating")],
        [InlineKeyboardButton(text="📅 Забронировать стол", callback_data="booking")],
        [InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile")],
    ])


def tournaments_keyboard(tournaments: list) -> InlineKeyboardMarkup:
    buttons = []
    for t in tournaments:
        status_icon = "🟢" if t["status"] == "upcoming" else "🔴"
        text = f"{status_icon} {t['name']} — {t['date']} {t['time']}"
        buttons.append([InlineKeyboardButton(
            text=text,
            callback_data=f"tournament_{t['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def tournament_detail_keyboard(tournament_id: int, is_registered: bool) -> InlineKeyboardMarkup:
    buttons = []
    if is_registered:
        buttons.append([InlineKeyboardButton(
            text="❌ Отменить регистрацию",
            callback_data=f"unreg_{tournament_id}"
        )])
    else:
        buttons.append([InlineKeyboardButton(
            text="✅ Зарегистрироваться",
            callback_data=f"reg_{tournament_id}"
        )])
    buttons.append([InlineKeyboardButton(
        text="👥 Участники",
        callback_data=f"participants_{tournament_id}"
    )])
    buttons.append([InlineKeyboardButton(text="◀️ К турнирам", callback_data="tournaments")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def booking_dates_keyboard(dates: list) -> InlineKeyboardMarkup:
    buttons = []
    for date in dates:
        buttons.append([InlineKeyboardButton(
            text=f"📅 {date}",
            callback_data=f"booking_date_{date}"
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def booking_slots_keyboard(date: str, slots: list) -> InlineKeyboardMarkup:
    buttons = []
    for slot in slots:
        if slot["available"]:
            text = f"🕐 {slot['time']} (мест: {slot['tables_left']})"
            buttons.append([InlineKeyboardButton(
                text=text,
                callback_data=f"booking_slot_{date}_{slot['time']}"
            )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="booking")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_booking_keyboard(date: str, time_slot: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_booking_{date}_{time_slot}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"booking_date_{date}")],
    ])


def profile_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 История игр", callback_data="game_history")],
        [InlineKeyboardButton(text="🔔 Уведомления", callback_data="toggle_notifications")],
        [InlineKeyboardButton(text="✏️ Изменить никнейм", callback_data="change_nickname")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")],
    ])


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать турнир", callback_data="admin_create_tournament")],
        [InlineKeyboardButton(text="📋 Управление турнирами", callback_data="admin_tournaments")],
        [InlineKeyboardButton(text="📅 Бронирования", callback_data="admin_bookings")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
    ])


def back_keyboard(callback: str = "back_main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data=callback)]
    ])
