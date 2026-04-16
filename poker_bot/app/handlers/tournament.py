from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from datetime import datetime

from app.database import (
    get_tournaments, get_tournament, register_player,
    unregister_player, is_registered, get_tournament_participants
)
from app.keyboards import tournaments_list_kb, tournament_detail_kb, back_kb

router = Router()


def fmt_date(dt_str: str) -> str:
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%d.%m / %H:%M")
    except Exception:
        return dt_str


@router.message(F.text == "🏆 Турниры")
async def show_tournaments(message: Message, player: dict):
    tournaments = await get_tournaments("upcoming")
    if not tournaments:
        await message.answer("На данный момент нет запланированных турниров.")
        return
    text = "🏆 <b>Ближайшие турниры:</b>\n\nВыбери турнир для подробностей:"
    await message.answer(text, reply_markup=tournaments_list_kb(tournaments, player["id"]))


@router.callback_query(F.data.startswith("tour:"))
async def tournament_detail(call: CallbackQuery, player: dict):
    tournament_id = int(call.data.split(":")[1])
    t = await get_tournament(tournament_id)
    if not t:
        await call.answer("Турнир не найден", show_alert=True)
        return

    registered = await is_registered(tournament_id, player["id"])
    filled = t.get("registered_count", 0)
    total = t.get("max_players", 100)
    status_icon = "🟢" if filled < total else "🔴"

    text = (
        f"🎯 <b>{t['title']}</b>\n\n"
        f"📍 {t.get('address', t.get('location', '—'))}\n"
        f"🕐 {fmt_date(t['start_time'])}\n"
        f"{status_icon} Мест: {filled}/{total}\n"
    )
    if t.get("buy_in"):
        text += f"💰 Бай-ин: {t['buy_in']} ₽\n"
    if t.get("prize_pool"):
        text += f"🏆 Призовой фонд: {t['prize_pool']}\n"
    if t.get("description"):
        text += f"\n{t['description']}\n"
    if registered:
        text += "\n✅ <i>Ты уже зарегистрирован</i>"

    await call.message.edit_text(
        text,
        reply_markup=tournament_detail_kb(tournament_id, registered)
    )


@router.callback_query(F.data.startswith("reg:"))
async def register(call: CallbackQuery, player: dict):
    tournament_id = int(call.data.split(":")[1])
    result = await register_player(tournament_id, player["id"])
    if result["ok"]:
        await call.answer("✅ Ты зарегистрирован!", show_alert=True)
        t = await get_tournament(tournament_id)
        registered = True
        filled = t.get("registered_count", 0)
        total = t.get("max_players", 100)
        text = (
            f"🎯 <b>{t['title']}</b>\n\n"
            f"📍 {t.get('address', t.get('location', '—'))}\n"
            f"🕐 {fmt_date(t['start_time'])}\n"
            f"🟢 Мест: {filled}/{total}\n"
            f"\n✅ <i>Ты уже зарегистрирован</i>"
        )
        await call.message.edit_text(
            text,
            reply_markup=tournament_detail_kb(tournament_id, registered)
        )
    elif result["reason"] == "already_registered":
        await call.answer("Ты уже зарегистрирован!", show_alert=True)
    elif result["reason"] == "full":
        await call.answer("❌ Турнир заполнен", show_alert=True)


@router.callback_query(F.data.startswith("unreg:"))
async def unregister(call: CallbackQuery, player: dict):
    tournament_id = int(call.data.split(":")[1])
    await unregister_player(tournament_id, player["id"])
    await call.answer("Регистрация отменена", show_alert=True)
    await tournament_detail(call, player)


@router.callback_query(F.data.startswith("participants:"))
async def show_participants(call: CallbackQuery):
    tournament_id = int(call.data.split(":")[1])
    participants = await get_tournament_participants(tournament_id)
    if not participants:
        await call.answer("Пока нет участников", show_alert=True)
        return
    lines = [f"👥 <b>Участники ({len(participants)}):</b>\n"]
    for i, p in enumerate(participants, 1):
        name = p["full_name"]
        username = f" @{p['username']}" if p.get("username") else ""
        lines.append(f"{i}. {name}{username}")
    await call.message.edit_text(
        "\n".join(lines),
        reply_markup=back_kb(f"tour:{tournament_id}")
    )


@router.callback_query(F.data == "back_tournaments")
async def back_tournaments(call: CallbackQuery, player: dict):
    tournaments = await get_tournaments("upcoming")
    await call.message.edit_text(
        "🏆 <b>Ближайшие турниры:</b>\n\nВыбери турнир:",
        reply_markup=tournaments_list_kb(tournaments, player["id"])
    )
