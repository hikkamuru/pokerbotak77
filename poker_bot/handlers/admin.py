from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from services.tournament_service import (
    create_tournament, get_upcoming_tournaments, get_tournament_by_id,
    record_result, finish_tournament, get_tournament_participants
)
from services.booking_service import get_all_bookings, confirm_booking
from services.player_service import get_all_players_for_broadcast
from utils.keyboards import admin_keyboard, back_keyboard
from config import config

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


class TournamentCreate(StatesGroup):
    name = State()
    date = State()
    time = State()
    max_players = State()
    address = State()
    description = State()


class RecordResult(StatesGroup):
    tournament_id = State()
    player_nickname = State()
    place = State()
    knockouts = State()


class BroadcastState(StatesGroup):
    message = State()


# ── Admin filter ─────────────────────────────────────────────────────────────
@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к панели администратора.")
        return
    await message.answer(
        "🔧 <b>Панель администратора</b>",
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )


# ── Create tournament ────────────────────────────────────────────────────────
@router.callback_query(F.data == "admin_create_tournament")
async def admin_create_tournament(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(TournamentCreate.name)
    await callback.message.edit_text("➕ Введите название турнира:")


@router.message(TournamentCreate.name)
async def tournament_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(TournamentCreate.date)
    await message.answer("📅 Введите дату (формат: 25.04.2025):")


@router.message(TournamentCreate.date)
async def tournament_date(message: Message, state: FSMContext):
    await state.update_data(date=message.text)
    await state.set_state(TournamentCreate.time)
    await message.answer("🕐 Введите время начала (формат: 19:00):")


@router.message(TournamentCreate.time)
async def tournament_time(message: Message, state: FSMContext):
    await state.update_data(time=message.text)
    await state.set_state(TournamentCreate.max_players)
    await message.answer("👥 Максимум участников:")


@router.message(TournamentCreate.max_players)
async def tournament_max_players(message: Message, state: FSMContext):
    try:
        max_p = int(message.text)
    except ValueError:
        await message.answer("❌ Введите число:")
        return
    await state.update_data(max_players=max_p)
    await state.set_state(TournamentCreate.address)
    await message.answer(f"📍 Адрес (Enter для стандартного {config.CLUB_ADDRESS}):")


@router.message(TournamentCreate.address)
async def tournament_address(message: Message, state: FSMContext):
    addr = message.text if message.text != "-" else config.CLUB_ADDRESS
    await state.update_data(address=addr, city=config.CLUB_CITY)
    await state.set_state(TournamentCreate.description)
    await message.answer("📝 Описание турнира (или '-' чтобы пропустить):")


@router.message(TournamentCreate.description)
async def tournament_description(message: Message, state: FSMContext):
    data = await state.get_data()
    desc = message.text if message.text != "-" else ""
    data["description"] = desc
    tournament_id = await create_tournament(data)
    await state.clear()
    await message.answer(
        f"✅ Турнир <b>{data['name']}</b> создан!\n"
        f"ID: {tournament_id}\n"
        f"📅 {data['date']} в {data['time']}\n"
        f"👥 Мест: {data['max_players']}\n"
        f"📍 {data['address']}",
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )


# ── Manage tournaments ───────────────────────────────────────────────────────
@router.callback_query(F.data == "admin_tournaments")
async def admin_tournaments(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    tournaments = await get_upcoming_tournaments()
    if not tournaments:
        await callback.message.edit_text(
            "Нет активных турниров.",
            reply_markup=admin_keyboard()
        )
        return
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = [[InlineKeyboardButton(
        text=f"⚙️ {t['name']} ({t['current_players']}/{t['max_players']})",
        callback_data=f"admin_t_{t['id']}"
    )] for t in tournaments]
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")])
    await callback.message.edit_text(
        "📋 Выберите турнир для управления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data.startswith("admin_t_"))
async def admin_tournament_detail(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    tournament_id = int(callback.data.split("_")[2])
    t = await get_tournament_by_id(tournament_id)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = [
        [InlineKeyboardButton(text="🏅 Записать результат", callback_data=f"admin_result_{tournament_id}")],
        [InlineKeyboardButton(text="🏁 Завершить турнир", callback_data=f"admin_finish_{tournament_id}")],
        [InlineKeyboardButton(text="👥 Список участников", callback_data=f"admin_parts_{tournament_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_tournaments")],
    ]
    await callback.message.edit_text(
        f"⚙️ <b>{t['name']}</b>\n"
        f"📅 {t['date']} {t['time']}\n"
        f"👥 {t['current_players']}/{t['max_players']}\n"
        f"Статус: {t['status']}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("admin_finish_"))
async def admin_finish_tournament(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    tournament_id = int(callback.data.split("_")[2])
    await finish_tournament(tournament_id)
    await callback.answer("✅ Турнир завершён!")
    await admin_tournaments(callback)


@router.callback_query(F.data.startswith("admin_parts_"))
async def admin_show_participants(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    tournament_id = int(callback.data.split("_")[2])
    parts = await get_tournament_participants(tournament_id)
    lines = [f"👥 Участники ({len(parts)}):\n"]
    for i, p in enumerate(parts, 1):
        nick = p.get("nickname") or p.get("full_name") or "—"
        place = f"🥇{p['place']}" if p.get("place") else "—"
        lines.append(f"{i}. {nick} | место: {place} | ноки: {p.get('knockouts', 0)}")
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=back_keyboard(f"admin_t_{tournament_id}")
    )


# ── Record results ───────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("admin_result_"))
async def admin_record_result_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    tournament_id = int(callback.data.split("_")[2])
    await state.update_data(tournament_id=tournament_id)
    await state.set_state(RecordResult.player_nickname)
    await callback.message.edit_text(
        "Введите Telegram ID или никнейм игрока:"
    )


@router.message(RecordResult.player_nickname)
async def rr_get_place(message: Message, state: FSMContext):
    from services.player_service import get_player_by_telegram_id
    from database.models import get_db
    text = message.text.strip()
    async with await get_db() as db:
        if text.isdigit():
            cursor = await db.execute(
                "SELECT * FROM players WHERE telegram_id=?", (int(text),)
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM players WHERE nickname=? OR full_name=?", (text, text)
            )
        player = await cursor.fetchone()
    if not player:
        await message.answer("❌ Игрок не найден. Попробуйте ещё раз:")
        return
    await state.update_data(player_id=dict(player)["id"])
    await state.set_state(RecordResult.place)
    await message.answer(f"✅ Игрок: {player['nickname'] or player['full_name']}\nВведите занятое место:")


@router.message(RecordResult.place)
async def rr_get_knockouts(message: Message, state: FSMContext):
    try:
        place = int(message.text)
    except ValueError:
        await message.answer("❌ Введите число:")
        return
    await state.update_data(place=place)
    await state.set_state(RecordResult.knockouts)
    await message.answer("Введите количество нокаутов (0 если нет):")


@router.message(RecordResult.knockouts)
async def rr_save(message: Message, state: FSMContext):
    try:
        knockouts = int(message.text)
    except ValueError:
        await message.answer("❌ Введите число:")
        return
    data = await state.get_data()
    result = await record_result(data["tournament_id"], data["player_id"], data["place"], knockouts)
    await state.clear()
    change = f"+{result['rating_change']}" if result['rating_change'] >= 0 else str(result['rating_change'])
    await message.answer(
        f"✅ Результат записан!\n"
        f"Место: {data['place']} | Ноки: {knockouts}\n"
        f"Изменение рейтинга: {change}\n"
        f"Новый рейтинг: {result['new_rating']}",
        reply_markup=admin_keyboard()
    )


# ── Bookings ─────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "admin_bookings")
async def admin_bookings(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    bookings = await get_all_bookings()
    if not bookings:
        await callback.message.edit_text(
            "📅 Активных бронирований нет.",
            reply_markup=admin_keyboard()
        )
        return
    lines = ["📅 <b>Активные бронирования:</b>\n"]
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    for b in bookings:
        nick = b.get("nickname") or b.get("full_name") or "—"
        lines.append(f"#{b['id']} {b['date']} {b['time_slot']} — {nick} (стол {b['table_number']}) [{b['status']}]")
        if b["status"] == "pending":
            buttons.append([InlineKeyboardButton(
                text=f"✅ Подтвердить #{b['id']}",
                callback_data=f"admin_confirm_booking_{b['id']}"
            )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")])
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("admin_confirm_booking_"))
async def admin_confirm_booking(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    booking_id = int(callback.data.split("_")[3])
    await confirm_booking(booking_id)
    await callback.answer("✅ Бронирование подтверждено!")
    await admin_bookings(callback)


# ── Broadcast ────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_prompt(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(BroadcastState.message)
    await callback.message.edit_text(
        "📢 Введите текст рассылки (поддерживает HTML):"
    )


@router.message(BroadcastState.message)
async def do_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    text = message.text
    player_ids = await get_all_players_for_broadcast()
    sent = 0
    failed = 0
    for tg_id in player_ids:
        try:
            await message.bot.send_message(tg_id, text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
    await state.clear()
    await message.answer(
        f"📢 Рассылка завершена!\n✅ Отправлено: {sent}\n❌ Ошибок: {failed}",
        reply_markup=admin_keyboard()
    )


@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "🔧 <b>Панель администратора</b>",
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )


# ── Admin stats ──────────────────────────────────────────────────────────────
@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    from database.models import get_db
    async with await get_db() as db:
        c = await db.execute("SELECT COUNT(*) FROM players")
        players_count = (await c.fetchone())[0]
        c = await db.execute("SELECT COUNT(*) FROM tournaments WHERE status='upcoming'")
        upcoming = (await c.fetchone())[0]
        c = await db.execute("SELECT COUNT(*) FROM tournaments WHERE status='finished'")
        finished = (await c.fetchone())[0]
        c = await db.execute("SELECT COUNT(*) FROM bookings WHERE status IN ('pending','confirmed')")
        bookings = (await c.fetchone())[0]
    await callback.message.edit_text(
        f"📊 <b>Статистика клуба</b>\n\n"
        f"👥 Игроков: {players_count}\n"
        f"🏆 Предстоящих турниров: {upcoming}\n"
        f"✅ Проведено турниров: {finished}\n"
        f"📅 Активных броней: {bookings}",
        reply_markup=back_keyboard("admin_back"),
        parse_mode="HTML"
    )
