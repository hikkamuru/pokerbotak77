from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.database import (
    create_tournament, get_tournaments, get_tournament,
    update_tournament_status, record_result,
    get_tournament_participants, update_booking_status,
    get_all_bookings, get_player_by_id
)
from app.keyboards import admin_panel_kb, back_kb
from config.settings import settings

router = Router()


def is_admin(tg_id: int) -> bool:
    return tg_id in settings.admin_list


class NewTournamentFSM(StatesGroup):
    title      = State()
    date_time  = State()
    location   = State()
    address    = State()
    max_players = State()
    buy_in     = State()
    description = State()


class RecordResultFSM(StatesGroup):
    tournament_id = State()
    player_tg     = State()
    place         = State()
    knockouts     = State()


# ─── ADMIN PANEL ────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "🛠 <b>Панель администратора</b>",
        reply_markup=admin_panel_kb()
    )


# ─── BOOKING APPROVALS ──────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:bookings")
async def list_bookings(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    bookings = await get_all_bookings("pending")
    if not bookings:
        await call.answer("Нет новых заявок", show_alert=True)
        return
    from app.keyboards import admin_booking_kb
    for b in bookings:
        text = (
            f"📬 Заявка #{b['id']}\n"
            f"👤 {b['full_name']}"
            + (f" @{b['username']}" if b.get("username") else "") + "\n"
            f"📅 {b['date']}  🕐 {b['time_slot']}\n"
            f"🪑 Мест: {b['seats']}"
        )
        await call.message.answer(text, reply_markup=admin_booking_kb(b["id"]))
    await call.answer()


@router.callback_query(F.data.startswith("admin_book_ok:"))
async def approve_booking(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    booking_id = int(call.data.split(":")[1])
    bookings = await get_all_bookings("pending")
    booking = next((b for b in bookings if b["id"] == booking_id), None)
    await update_booking_status(booking_id, "approved")
    await call.message.edit_text(f"✅ Бронь #{booking_id} одобрена")
    if booking:
        try:
            await call.bot.send_message(
                booking["tg_id"],
                f"✅ Твоя заявка на {booking['date']} в {booking['time_slot']} подтверждена!"
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("admin_book_no:"))
async def reject_booking(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    booking_id = int(call.data.split(":")[1])
    bookings = await get_all_bookings("pending")
    booking = next((b for b in bookings if b["id"] == booking_id), None)
    await update_booking_status(booking_id, "rejected")
    await call.message.edit_text(f"❌ Бронь #{booking_id} отклонена")
    if booking:
        try:
            await call.bot.send_message(
                booking["tg_id"],
                f"❌ Заявка на {booking['date']} в {booking['time_slot']} отклонена. Свяжись с администратором."
            )
        except Exception:
            pass


# ─── CREATE TOURNAMENT ──────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:new_tour")
async def new_tour_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await call.message.answer("Введи название турнира:")
    await state.set_state(NewTournamentFSM.title)


@router.message(NewTournamentFSM.title)
async def new_tour_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("Дата и время (формат: 2025-12-31 19:00):")
    await state.set_state(NewTournamentFSM.date_time)


@router.message(NewTournamentFSM.date_time)
async def new_tour_datetime(message: Message, state: FSMContext):
    await state.update_data(start_time=message.text)
    await message.answer("Локация (название места):")
    await state.set_state(NewTournamentFSM.location)


@router.message(NewTournamentFSM.location)
async def new_tour_location(message: Message, state: FSMContext):
    await state.update_data(location=message.text)
    await message.answer("Адрес:")
    await state.set_state(NewTournamentFSM.address)


@router.message(NewTournamentFSM.address)
async def new_tour_address(message: Message, state: FSMContext):
    await state.update_data(address=message.text)
    await message.answer("Максимум участников:")
    await state.set_state(NewTournamentFSM.max_players)


@router.message(NewTournamentFSM.max_players)
async def new_tour_max(message: Message, state: FSMContext):
    await state.update_data(max_players=int(message.text or 100))
    await message.answer("Бай-ин (0 если бесплатно):")
    await state.set_state(NewTournamentFSM.buy_in)


@router.message(NewTournamentFSM.buy_in)
async def new_tour_buyin(message: Message, state: FSMContext):
    await state.update_data(buy_in=int(message.text or 0))
    await message.answer("Описание (или отправь '-' чтобы пропустить):")
    await state.set_state(NewTournamentFSM.description)


@router.message(NewTournamentFSM.description)
async def new_tour_desc(message: Message, state: FSMContext):
    data = await state.get_data()
    desc = message.text if message.text != "-" else None
    data["description"] = desc
    tour_id = await create_tournament(data)
    await state.clear()
    await message.answer(
        f"✅ Турнир <b>{data['title']}</b> создан!\n"
        f"ID: <code>{tour_id}</code>"
    )


# ─── RECORD RESULT ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:finish_tour")
async def finish_tour_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    tournaments = await get_tournaments("upcoming")
    if not tournaments:
        await call.answer("Нет активных турниров", show_alert=True)
        return
    lines = ["Введи ID турнира для завершения:\n"]
    for t in tournaments:
        lines.append(f"<code>{t['id']}</code> — {t['title']}  {t['start_time'][:16]}")
    await call.message.answer("\n".join(lines))
    await state.set_state(RecordResultFSM.tournament_id)


@router.message(RecordResultFSM.tournament_id)
async def finish_tour_id(message: Message, state: FSMContext):
    await state.update_data(tournament_id=int(message.text))
    await message.answer(
        "Введи Telegram ID игрока, место и ноки через пробел:\n"
        "Пример: <code>123456789 1 5</code>\n"
        "Или 'стоп' чтобы завершить ввод"
    )
    await state.set_state(RecordResultFSM.player_tg)


@router.message(RecordResultFSM.player_tg)
async def finish_tour_result(message: Message, state: FSMContext):
    if message.text.lower() == "стоп":
        data = await state.get_data()
        await update_tournament_status(data["tournament_id"], "finished")
        await state.clear()
        await message.answer("✅ Турнир завершён, результаты записаны!")
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Неверный формат. Пример: 123456789 1 5")
        return
    from app.database import get_player_by_tg
    tg_id = int(parts[0])
    place = int(parts[1])
    knockouts = int(parts[2]) if len(parts) > 2 else 0
    player = await get_player_by_tg(tg_id)
    if not player:
        await message.answer(f"Игрок {tg_id} не найден в базе")
        return
    data = await state.get_data()
    await record_result(data["tournament_id"], player["id"], place, knockouts)
    await message.answer(
        f"✅ Записано: {player['full_name']} — место {place}, ноки {knockouts}\n"
        f"Следующий игрок или 'стоп':"
    )


# ─── EXPORT ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:export")
async def export_rating(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    from app.database import get_leaderboard
    import io
    players = await get_leaderboard(limit=500)
    lines = ["#,Имя,Username,Рейтинг,Ноки,PRO,Игр,Побед"]
    for i, p in enumerate(players, 1):
        lines.append(
            f"{i},{p['full_name']},{p.get('username','')},{p['rating']:.0f},"
            f"{p['knockouts']},{p['pro_score']:.0f},{p['games_count']},{p['wins_count']}"
        )
    csv_data = "\n".join(lines).encode("utf-8-sig")
    from aiogram.types import BufferedInputFile
    await call.message.answer_document(
        BufferedInputFile(csv_data, filename="rating.csv"),
        caption="📊 Экспорт рейтинга"
    )
    await call.answer()


# ─── BROADCAST ──────────────────────────────────────────────────────────────

class BroadcastFSM(StatesGroup):
    waiting_text = State()


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "📣 <b>Рассылка</b>\n\nОтправь текст сообщения для всех игроков.\n"
        "Поддерживается HTML-форматирование.\n\n"
        "Отправь /cancel для отмены."
    )
    await state.set_state(BroadcastFSM.waiting_text)


@router.message(BroadcastFSM.waiting_text)
async def do_broadcast(message: Message, state: FSMContext):
    if message.text and message.text.startswith("/cancel"):
        await state.clear()
        await message.answer("Рассылка отменена.")
        return
    await state.clear()
    status_msg = await message.answer("⏳ Отправляю...")
    from app.services.broadcast import broadcast
    result = await broadcast(message.bot, message.text or message.caption or "")
    await status_msg.edit_text(
        f"✅ <b>Рассылка завершена</b>\n\n"
        f"📤 Отправлено: {result['sent']}\n"
        f"❌ Ошибок: {result['failed']}\n"
        f"👥 Всего: {result['total']}"
    )


# ─── CLUB STATS ─────────────────────────────────────────────────────────────

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    import aiosqlite
    from app.database import DB_PATH
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        players_row = await db.execute("SELECT COUNT(*) as cnt FROM players WHERE tg_id > 0")
        players_cnt = (await players_row.fetchone())["cnt"]

        tours_row = await db.execute("SELECT COUNT(*) as cnt FROM tournaments WHERE status='upcoming'")
        tours_cnt = (await tours_row.fetchone())["cnt"]

        finished_row = await db.execute("SELECT COUNT(*) as cnt FROM tournaments WHERE status='finished'")
        finished_cnt = (await finished_row.fetchone())["cnt"]

        bookings_row = await db.execute("SELECT COUNT(*) as cnt FROM bookings WHERE status='pending'")
        bookings_cnt = (await bookings_row.fetchone())["cnt"]

        games_row = await db.execute("SELECT COUNT(*) as cnt FROM game_results")
        games_cnt = (await games_row.fetchone())["cnt"]

    await message.answer(
        f"📊 <b>Статистика клуба</b>\n\n"
        f"👥 Игроков в базе: <b>{players_cnt}</b>\n"
        f"🏆 Турниров предстоит: <b>{tours_cnt}</b>\n"
        f"✅ Турниров завершено: <b>{finished_cnt}</b>\n"
        f"🃏 Сыграно партий: <b>{games_cnt}</b>\n"
        f"📅 Заявок на бронь: <b>{bookings_cnt}</b>"
    )
