from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta

from app.database import create_booking
from app.keyboards import booking_time_kb, booking_seats_kb, confirm_booking_kb, main_menu_kb

router = Router()


class BookingFSM(StatesGroup):
    choosing_date = State()
    choosing_time = State()
    choosing_seats = State()
    confirming = State()


def next_days(n: int = 7) -> list[str]:
    today = datetime.now().date()
    return [(today + timedelta(days=i)).strftime("%d.%m.%Y") for i in range(n)]


@router.message(F.text == "📅 Забронировать стол")
async def start_booking(message: Message, state: FSMContext):
    days = next_days(7)
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    for day in days:
        kb.button(text=day, callback_data=f"date:{day}")
    kb.button(text="◀️ Отмена", callback_data="cancel_booking")
    kb.adjust(3, 3, 1)
    await message.answer(
        "📅 <b>Бронирование стола</b>\n\nВыбери дату:",
        reply_markup=kb.as_markup()
    )
    await state.set_state(BookingFSM.choosing_date)


@router.callback_query(F.data.startswith("date:"))
async def choose_date(call: CallbackQuery, state: FSMContext):
    date = call.data.split(":")[1]
    await state.update_data(date=date)
    await call.message.edit_text(
        f"📅 Дата: <b>{date}</b>\n\nВыбери время:",
        reply_markup=booking_time_kb()
    )
    await state.set_state(BookingFSM.choosing_time)


@router.callback_query(F.data.startswith("slot:"))
async def choose_slot(call: CallbackQuery, state: FSMContext):
    slot = call.data.split(":")[1]
    await state.update_data(time_slot=slot)
    data = await state.get_data()
    await call.message.edit_text(
        f"📅 Дата: <b>{data['date']}</b>  🕐 Время: <b>{slot}</b>\n\nСколько мест?",
        reply_markup=booking_seats_kb()
    )
    await state.set_state(BookingFSM.choosing_seats)


@router.callback_query(F.data.startswith("seats:"))
async def choose_seats(call: CallbackQuery, state: FSMContext):
    seats = int(call.data.split(":")[1])
    await state.update_data(seats=seats)
    data = await state.get_data()
    await call.message.edit_text(
        f"📋 <b>Подтверди бронирование:</b>\n\n"
        f"📅 Дата: {data['date']}\n"
        f"🕐 Время: {data['time_slot']}\n"
        f"🪑 Мест: {seats}\n",
        reply_markup=confirm_booking_kb()
    )
    await state.set_state(BookingFSM.confirming)


@router.callback_query(F.data == "confirm_booking")
async def confirm_booking(call: CallbackQuery, state: FSMContext, player: dict):
    data = await state.get_data()
    booking_id = await create_booking(
        player_id=player["id"],
        date=data["date"],
        time_slot=data["time_slot"],
        seats=data.get("seats", 1),
    )
    await state.clear()

    # Notify admins
    from config.settings import settings
    from aiogram import Bot
    bot: Bot = call.bot
    admin_text = (
        f"📬 <b>Новая заявка на бронь #{booking_id}</b>\n\n"
        f"👤 {player['full_name']}"
        + (f" @{player['username']}" if player.get("username") else "") + "\n"
        f"📅 {data['date']}  🕐 {data['time_slot']}\n"
        f"🪑 Мест: {data.get('seats', 1)}"
    )
    from app.keyboards import admin_booking_kb
    for admin_id in settings.admin_list:
        try:
            await bot.send_message(admin_id, admin_text, reply_markup=admin_booking_kb(booking_id))
        except Exception:
            pass

    await call.message.edit_text(
        f"✅ <b>Бронирование отправлено!</b>\n\n"
        f"📅 {data['date']}  🕐 {data['time_slot']}\n"
        f"🪑 Мест: {data.get('seats', 1)}\n\n"
        f"Администратор скоро подтвердит твою заявку."
    )


@router.callback_query(F.data == "cancel_booking")
async def cancel_booking(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Бронирование отменено.")
