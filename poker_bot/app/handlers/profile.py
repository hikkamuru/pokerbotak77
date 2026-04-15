from aiogram import Router, F
from aiogram.types import Message

from app.database import get_player_by_tg, get_leaderboard, get_player_tournaments

router = Router()


@router.message(F.text == "👤 Мой профиль")
async def show_profile(message: Message, player: dict):
    p = await get_player_by_tg(message.from_user.id)
    history = await get_player_tournaments(p["id"])
    finished = [g for g in history if g.get("place")]
    best_place = min((g["place"] for g in finished), default=None)

    text = (
        f"👤 <b>{p['full_name']}</b>"
        + (f" @{p['username']}" if p.get("username") else "") + "\n\n"
        f"📍 Город: {p.get('city', 'Не указан')}\n"
        f"⭐ Рейтинг: <b>{p['rating']:.0f}</b>\n"
        f"💥 Ноки: <b>{p['knockouts']}</b>\n"
        f"🃏 Игр сыграно: <b>{p['games_count']}</b>\n"
        f"🏆 Победы: <b>{p['wins_count']}</b>\n"
    )
    if best_place:
        text += f"🎯 Лучшее место: <b>{best_place}</b>\n"
    if p.get("free_entry"):
        text += f"🎟 Free Entry: <b>{p['free_entry']}</b>\n"

    await message.answer(text)


@router.message(F.text == "⭐ Рейтинг")
async def show_rating(message: Message):
    players = await get_leaderboard(limit=20)
    if not players:
        await message.answer("Рейтинг пока пуст.")
        return
    lines = ["⭐ <b>Рейтинг игроков (Топ-20):</b>\n"]
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for i, p in enumerate(players, 1):
        medal = medals.get(i, f"{i}.")
        name = p["full_name"]
        username = f" @{p['username']}" if p.get("username") else ""
        lines.append(
            f"{medal} {name}{username}  •  "
            f"⭐{p['rating']:.0f}  💥{p['knockouts']}"
        )
    await message.answer("\n".join(lines))
