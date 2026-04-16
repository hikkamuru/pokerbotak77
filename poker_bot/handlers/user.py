from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from services.player_service import get_or_create_player, get_player_by_telegram_id, get_player_history, update_push_notifications, update_player_nickname
from services.tournament_service import get_upcoming_tournaments, get_past_tournaments, get_tournament_by_id, register_player, unregister_player, is_player_registered, get_tournament_participants
from services.booking_service import get_available_slots, create_booking, get_player_bookings, cancel_booking
from utils.keyboards import (
    main_menu_keyboard, tournaments_keyboard, tournament_detail_keyboard,
    booking_dates_keyboard, booking_slots_keyboard, confirm_booking_keyboard,
    profile_keyboard, back_keyboard
)
from config import config
from datetime import datetime, timedelta

router = Router()


class NicknameState(StatesGroup):
    waiting_nickname = State()


def get_next_dates(days: int = 7) -> list:
    dates = []
    today = datetime.now()
    for i in range(days):
        d = today + timedelta(days=i)
        dates.append(d.strftime("%d.%m.%Y"))
    return dates


# ── /start ──────────────────────────────────────────────────────────────────
@router.message(CommandStart())
async def cmd_start(message: Message):
    player = await get_or_create_player(
        telegram_id=message.from_user.id,
        username=message.from_user.username or "",
        full_name=message.from_user.full_name or ""
    )
    name = player.get("nickname") or player.get("full_name") or "игрок"
    text = (
        f"👋 Привет, <b>{name}</b>!\n\n"
        f"Добро пожаловать в <b>{config.CLUB_NAME}</b> — покерный клуб <b>{config.CLUB_CITY}</b>.\n\n"
        f"Здесь ты можешь:\n"
        f"• 🏆 Регистрироваться на турниры\n"
        f"• 📅 Бронировать столики\n"
        f"• ⭐ Следить за своим рейтингом\n"
        f"• 📊 Смотреть историю игр"
    )
    await message.answer(
        text,
        reply_markup=main_menu_keyboard(config.WEBAPP_URL),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.edit_text(
        f"🃏 <b>{config.CLUB_NAME}</b>\n\nВыберите раздел:",
        reply_markup=main_menu_keyboard(config.WEBAPP_URL),
        parse_mode="HTML"
    )


# ── TOURNAMENTS ──────────────────────────────────────────────────────────────
@router.callback_query(F.data == "tournaments")
async def show_tournaments(callback: CallbackQuery):
    tournaments = await get_upcoming_tournaments()
    if not tournaments:
        await callback.message.edit_text(
            "😔 Ближайших турниров пока нет.\n\nСледите за обновлениями!",
            reply_markup=back_keyboard()
        )
        return
    await callback.message.edit_text(
        "🏆 <b>Предстоящие турниры</b>\n\nВыберите турнир для подробностей:",
        reply_markup=tournaments_keyboard(tournaments),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("tournament_"))
async def show_tournament_detail(callback: CallbackQuery):
    tournament_id = int(callback.data.split("_")[1])
    t = await get_tournament_by_id(tournament_id)
    if not t:
        await callback.answer("Турнир не найден")
        return
    player = await get_player_by_telegram_id(callback.from_user.id)
    is_reg = False
    if player:
        is_reg = await is_player_registered(tournament_id, player["id"])
    spots_left = t["max_players"] - t["current_players"]
    status_text = "✅ Вы зарегистрированы" if is_reg else f"🎯 Свободных мест: {spots_left}/{t['max_players']}"
    text = (
        f"🏆 <b>{t['name']}</b>\n\n"
        f"📍 {t['address']}\n"
        f"📅 {t['date']} в {t['time']}\n"
        f"👥 {t['current_players']}/{t['max_players']} участников\n"
        f"{status_text}\n"
    )
    if t.get("description"):
        text += f"\n📝 {t['description']}"
    await callback.message.edit_text(
        text,
        reply_markup=tournament_detail_keyboard(tournament_id, is_reg),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("reg_"))
async def register_for_tournament(callback: CallbackQuery):
    tournament_id = int(callback.data.split("_")[1])
    player = await get_player_by_telegram_id(callback.from_user.id)
    if not player:
        await callback.answer("Профиль не найден, напишите /start")
        return
    result = await register_player(tournament_id, player["id"])
    messages = {
        "success": "✅ Вы успешно зарегистрированы на турнир!",
        "already_registered": "ℹ️ Вы уже зарегистрированы на этот турнир",
        "full": "😔 К сожалению, все места заняты",
        "not_found": "❌ Турнир не найден"
    }
    await callback.answer(messages.get(result, "Ошибка"))
    if result in ("success", "already_registered"):
        await show_tournament_detail(callback)


@router.callback_query(F.data.startswith("unreg_"))
async def unregister_from_tournament(callback: CallbackQuery):
    tournament_id = int(callback.data.split("_")[1])
    player = await get_player_by_telegram_id(callback.from_user.id)
    if not player:
        await callback.answer("Профиль не найден")
        return
    ok = await unregister_player(tournament_id, player["id"])
    await callback.answer("✅ Регистрация отменена" if ok else "❌ Вы не были зарегистрированы")
    await show_tournament_detail(callback)


@router.callback_query(F.data.startswith("participants_"))
async def show_participants(callback: CallbackQuery):
    tournament_id = int(callback.data.split("_")[1])
    participants = await get_tournament_participants(tournament_id)
    t = await get_tournament_by_id(tournament_id)
    if not participants:
        await callback.answer("Пока нет участников")
        return
    lines = [f"👥 <b>Участники: {t['name']}</b>\n"]
    for i, p in enumerate(participants[:30], 1):
        nick = p.get("nickname") or p.get("full_name") or "Аноним"
        lines.append(f"{i}. {nick} — ⭐{p['rating']}")
    if len(participants) > 30:
        lines.append(f"\n...и ещё {len(participants) - 30} участников")
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=back_keyboard(f"tournament_{tournament_id}"),
        parse_mode="HTML"
    )


# ── RATING ───────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "rating")
async def show_rating(callback: CallbackQuery):
    from services.player_service import get_leaderboard
    leaders = await get_leaderboard(limit=20)
    if not leaders:
        await callback.message.edit_text(
            "📊 Рейтинг пока пуст — сыграйте первый турнир!",
            reply_markup=back_keyboard()
        )
        return
    lines = ["⭐ <b>Рейтинг игроков</b>\n"]
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for i, p in enumerate(leaders, 1):
        medal = medals.get(i, f"{i}.")
        nick = p.get("nickname") or p.get("full_name") or "Аноним"
        lines.append(
            f"{medal} <b>{nick}</b> — {p['rating']} очков | "
            f"Ноки: {p['knockouts']} | PRO: {p['pro_rating']:.1f}"
        )
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )


# ── BOOKING ──────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "booking")
async def show_booking(callback: CallbackQuery):
    dates = get_next_dates(7)
    await callback.message.edit_text(
        "📅 <b>Бронирование столика</b>\n\nВыберите дату:",
        reply_markup=booking_dates_keyboard(dates),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("booking_date_"))
async def show_booking_slots(callback: CallbackQuery):
    date = callback.data.replace("booking_date_", "")
    slots = await get_available_slots(date)
    available = [s for s in slots if s["available"]]
    if not available:
        await callback.message.edit_text(
            f"😔 На {date} все столики заняты.\n\nВыберите другую дату:",
            reply_markup=booking_dates_keyboard(get_next_dates(7))
        )
        return
    await callback.message.edit_text(
        f"📅 <b>{date}</b>\n\nВыберите время:",
        reply_markup=booking_slots_keyboard(date, slots),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("booking_slot_"))
async def confirm_booking_prompt(callback: CallbackQuery):
    parts = callback.data.split("_")
    date = parts[2]
    time_slot = parts[3]
    await callback.message.edit_text(
        f"📅 <b>Подтверждение брони</b>\n\n"
        f"Дата: {date}\n"
        f"Время: {time_slot}\n\n"
        f"Подтвердить бронирование?",
        reply_markup=confirm_booking_keyboard(date, time_slot),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("confirm_booking_"))
async def do_booking(callback: CallbackQuery):
    parts = callback.data.split("_")
    date = parts[2]
    time_slot = parts[3]
    player = await get_player_by_telegram_id(callback.from_user.id)
    if not player:
        await callback.answer("Профиль не найден, напишите /start")
        return
    booking_id = await create_booking(player["id"], date, time_slot)
    if booking_id:
        await callback.message.edit_text(
            f"✅ <b>Стол забронирован!</b>\n\n"
            f"📅 {date} в {time_slot}\n"
            f"🔖 Номер брони: #{booking_id}\n\n"
            f"Ждём вас в <b>{config.CLUB_NAME}</b>!\n"
            f"📍 {config.CLUB_ADDRESS}",
            reply_markup=back_keyboard(),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            "😔 К сожалению, на это время уже нет свободных мест.\n\nВыберите другое время.",
            reply_markup=booking_dates_keyboard(get_next_dates(7))
        )


# ── PROFILE ──────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery):
    player = await get_player_by_telegram_id(callback.from_user.id)
    if not player:
        await callback.answer("Профиль не найден")
        return
    from services.player_service import get_player_rank
    rank = await get_player_rank(player["id"])
    notif = "🔔 Вкл" if player["push_notifications"] else "🔕 Выкл"
    text = (
        f"👤 <b>Мой профиль</b>\n\n"
        f"📛 Никнейм: <b>{player.get('nickname') or 'не задан'}</b>\n"
        f"🏙 Город: {player.get('city', 'Москва')}\n"
        f"⭐ Рейтинг: <b>{player['rating']}</b> (#{rank})\n"
        f"🃏 Игр сыграно: {player['games_played']}\n"
        f"🏆 Победы: {player['games_won']}\n"
        f"💥 Нокауты: {player['knockouts']}\n"
        f"📊 PRO очки: {player['pro_rating']:.2f}\n"
        f"🎟 Free Entry: {player['free_entries']}\n"
        f"Уведомления: {notif}"
    )
    await callback.message.edit_text(text, reply_markup=profile_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "game_history")
async def show_game_history(callback: CallbackQuery):
    player = await get_player_by_telegram_id(callback.from_user.id)
    if not player:
        await callback.answer("Профиль не найден")
        return
    history = await get_player_history(player["id"])
    if not history:
        await callback.message.edit_text(
            "📊 У вас пока нет истории игр.",
            reply_markup=back_keyboard("profile")
        )
        return
    lines = ["📊 <b>История игр</b>\n"]
    for h in history:
        change = f"+{h['rating_change']}" if h['rating_change'] >= 0 else str(h['rating_change'])
        lines.append(
            f"🏆 <b>{h['tournament_name']}</b>\n"
            f"   📅 {h['date']} | 🥇 Место: {h['place']} | "
            f"💥 Ноки: {h['knockouts']} | ⭐ {change}\n"
        )
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=back_keyboard("profile"),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "toggle_notifications")
async def toggle_notifications(callback: CallbackQuery):
    player = await get_player_by_telegram_id(callback.from_user.id)
    if not player:
        return
    new_val = not bool(player["push_notifications"])
    await update_push_notifications(callback.from_user.id, new_val)
    status = "включены 🔔" if new_val else "выключены 🔕"
    await callback.answer(f"Уведомления {status}")
    await show_profile(callback)


@router.callback_query(F.data == "change_nickname")
async def change_nickname_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(NicknameState.waiting_nickname)
    await callback.message.edit_text(
        "✏️ Введите новый никнейм (3–20 символов, только буквы, цифры и _):",
        reply_markup=back_keyboard("profile")
    )


@router.message(NicknameState.waiting_nickname)
async def process_nickname(message: Message, state: FSMContext):
    nickname = message.text.strip()
    if not (3 <= len(nickname) <= 20):
        await message.answer("❌ Никнейм должен быть от 3 до 20 символов. Попробуйте ещё раз:")
        return
    ok = await update_player_nickname(message.from_user.id, nickname)
    await state.clear()
    if ok:
        await message.answer(
            f"✅ Никнейм изменён на <b>{nickname}</b>!",
            reply_markup=back_keyboard("profile"),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "❌ Этот никнейм уже занят. Выберите другой:",
        )
        await state.set_state(NicknameState.waiting_nickname)
