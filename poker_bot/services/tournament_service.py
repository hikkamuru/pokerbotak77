from database.models import get_db
from typing import Optional
import math


async def get_upcoming_tournaments() -> list:
    async with await get_db() as db:
        cursor = await db.execute(
            """SELECT * FROM tournaments 
               WHERE status IN ('upcoming', 'active')
               ORDER BY date ASC, time ASC"""
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_past_tournaments(limit: int = 20) -> list:
    async with await get_db() as db:
        cursor = await db.execute(
            """SELECT * FROM tournaments 
               WHERE status = 'finished'
               ORDER BY date DESC, time DESC
               LIMIT ?""",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_tournament_by_id(tournament_id: int) -> Optional[dict]:
    async with await get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM tournaments WHERE id = ?", (tournament_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_nearest_tournament() -> Optional[dict]:
    async with await get_db() as db:
        cursor = await db.execute(
            """SELECT * FROM tournaments 
               WHERE status = 'upcoming'
               ORDER BY date ASC, time ASC
               LIMIT 1"""
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def create_tournament(data: dict) -> int:
    async with await get_db() as db:
        cursor = await db.execute(
            """INSERT INTO tournaments 
               (name, description, rules, address, city, max_players, date, time, buy_in, prize_pool, banner_url)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["name"], data.get("description", ""), data.get("rules", ""),
                data.get("address", ""), data.get("city", "Москва"),
                data.get("max_players", 100), data["date"], data["time"],
                data.get("buy_in", 0), data.get("prize_pool", ""),
                data.get("banner_url", "")
            )
        )
        await db.commit()
        return cursor.lastrowid


async def update_tournament(tournament_id: int, data: dict):
    async with await get_db() as db:
        fields = []
        values = []
        for key, val in data.items():
            fields.append(f"{key}=?")
            values.append(val)
        values.append(tournament_id)
        await db.execute(
            f"UPDATE tournaments SET {', '.join(fields)} WHERE id=?",
            values
        )
        await db.commit()


async def register_player(tournament_id: int, player_id: int) -> str:
    async with await get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM tournaments WHERE id = ?", (tournament_id,)
        )
        tournament = await cursor.fetchone()
        if not tournament:
            return "not_found"
        if tournament["current_players"] >= tournament["max_players"]:
            return "full"
        cursor = await db.execute(
            "SELECT id FROM tournament_registrations WHERE tournament_id=? AND player_id=?",
            (tournament_id, player_id)
        )
        if await cursor.fetchone():
            return "already_registered"
        await db.execute(
            "INSERT INTO tournament_registrations (tournament_id, player_id) VALUES (?, ?)",
            (tournament_id, player_id)
        )
        await db.execute(
            "UPDATE tournaments SET current_players = current_players + 1 WHERE id = ?",
            (tournament_id,)
        )
        await db.commit()
        return "success"


async def unregister_player(tournament_id: int, player_id: int) -> bool:
    async with await get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM tournament_registrations WHERE tournament_id=? AND player_id=?",
            (tournament_id, player_id)
        )
        if not await cursor.fetchone():
            return False
        await db.execute(
            "DELETE FROM tournament_registrations WHERE tournament_id=? AND player_id=?",
            (tournament_id, player_id)
        )
        await db.execute(
            "UPDATE tournaments SET current_players = MAX(0, current_players - 1) WHERE id = ?",
            (tournament_id,)
        )
        await db.commit()
        return True


async def is_player_registered(tournament_id: int, player_id: int) -> bool:
    async with await get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM tournament_registrations WHERE tournament_id=? AND player_id=?",
            (tournament_id, player_id)
        )
        return bool(await cursor.fetchone())


async def get_tournament_participants(tournament_id: int) -> list:
    async with await get_db() as db:
        cursor = await db.execute(
            """SELECT p.*, tr.registered_at, tr.place, tr.knockouts
               FROM tournament_registrations tr
               JOIN players p ON tr.player_id = p.id
               WHERE tr.tournament_id = ?
               ORDER BY tr.registered_at ASC""",
            (tournament_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def record_result(tournament_id: int, player_id: int, place: int, knockouts: int = 0) -> dict:
    """Record tournament result and update player rating (ELO-like system)"""
    async with await get_db() as db:
        cursor = await db.execute(
            "SELECT max_players, current_players FROM tournaments WHERE id=?",
            (tournament_id,)
        )
        tournament = await cursor.fetchone()
        if not tournament:
            return {}
        total = tournament["current_players"] or 1
        cursor = await db.execute("SELECT * FROM players WHERE id=?", (player_id,))
        player = await cursor.fetchone()
        if not player:
            return {}

        # Rating calculation: top 30% = positive, rest = negative
        percentile = place / total
        if percentile <= 0.1:
            rating_change = 100
        elif percentile <= 0.3:
            rating_change = 50
        elif percentile <= 0.5:
            rating_change = 20
        elif percentile <= 0.7:
            rating_change = 0
        else:
            rating_change = -20

        # PRO points = knockouts * multiplier
        pro_change = round(knockouts * (1 + (1 / math.log(total + 1))), 2)

        # Save result
        await db.execute(
            """INSERT INTO game_results (tournament_id, player_id, place, knockouts, rating_change, pro_change)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (tournament_id, player_id, place, knockouts, rating_change, pro_change)
        )
        # Update registration record
        await db.execute(
            "UPDATE tournament_registrations SET place=?, knockouts=? WHERE tournament_id=? AND player_id=?",
            (place, knockouts, tournament_id, player_id)
        )
        # Update player stats
        new_rating = max(0, player["rating"] + rating_change)
        won = 1 if place == 1 else 0
        await db.execute(
            """UPDATE players SET 
               rating=?, 
               pro_rating=pro_rating+?,
               knockouts=knockouts+?,
               games_played=games_played+1,
               games_won=games_won+?,
               updated_at=datetime('now')
               WHERE id=?""",
            (new_rating, pro_change, knockouts, won, player_id)
        )
        await db.commit()
        return {"rating_change": rating_change, "pro_change": pro_change, "new_rating": new_rating}


async def finish_tournament(tournament_id: int):
    async with await get_db() as db:
        await db.execute(
            "UPDATE tournaments SET status='finished' WHERE id=?",
            (tournament_id,)
        )
        await db.commit()


async def get_tournament_stats(tournament_id: int) -> dict:
    async with await get_db() as db:
        cursor = await db.execute(
            """SELECT COUNT(*) as total, 
                      SUM(knockouts) as total_knockouts
               FROM tournament_registrations
               WHERE tournament_id=?""",
            (tournament_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else {}
