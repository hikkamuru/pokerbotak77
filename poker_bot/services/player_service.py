from database.models import get_db
from typing import Optional


async def get_or_create_player(telegram_id: int, username: str, full_name: str) -> dict:
    async with await get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM players WHERE telegram_id = ?", (telegram_id,)
        )
        player = await cursor.fetchone()
        if player:
            await db.execute(
                "UPDATE players SET username=?, full_name=?, updated_at=datetime('now') WHERE telegram_id=?",
                (username, full_name, telegram_id)
            )
            await db.commit()
            cursor = await db.execute(
                "SELECT * FROM players WHERE telegram_id = ?", (telegram_id,)
            )
            player = await cursor.fetchone()
            return dict(player)
        await db.execute(
            """INSERT INTO players (telegram_id, username, full_name, nickname)
               VALUES (?, ?, ?, ?)""",
            (telegram_id, username, full_name, username or full_name)
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM players WHERE telegram_id = ?", (telegram_id,)
        )
        player = await cursor.fetchone()
        return dict(player)


async def get_player_by_telegram_id(telegram_id: int) -> Optional[dict]:
    async with await get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM players WHERE telegram_id = ?", (telegram_id,)
        )
        player = await cursor.fetchone()
        return dict(player) if player else None


async def get_player_by_id(player_id: int) -> Optional[dict]:
    async with await get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM players WHERE id = ?", (player_id,)
        )
        player = await cursor.fetchone()
        return dict(player) if player else None


async def update_player_nickname(telegram_id: int, nickname: str) -> bool:
    async with await get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM players WHERE nickname = ? AND telegram_id != ?",
            (nickname, telegram_id)
        )
        existing = await cursor.fetchone()
        if existing:
            return False
        await db.execute(
            "UPDATE players SET nickname=?, updated_at=datetime('now') WHERE telegram_id=?",
            (nickname, telegram_id)
        )
        await db.commit()
        return True


async def get_leaderboard(limit: int = 50, season: str = None) -> list:
    async with await get_db() as db:
        cursor = await db.execute(
            """SELECT p.*, 
                      ROW_NUMBER() OVER (ORDER BY p.rating DESC) as rank
               FROM players p
               WHERE p.games_played > 0
               ORDER BY p.rating DESC
               LIMIT ?""",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_player_rank(player_id: int) -> int:
    async with await get_db() as db:
        cursor = await db.execute(
            """SELECT COUNT(*) + 1 as rank FROM players 
               WHERE rating > (SELECT rating FROM players WHERE id = ?)
               AND games_played > 0""",
            (player_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_player_history(player_id: int, limit: int = 20) -> list:
    async with await get_db() as db:
        cursor = await db.execute(
            """SELECT gr.*, t.name as tournament_name, t.date, t.time
               FROM game_results gr
               JOIN tournaments t ON gr.tournament_id = t.id
               WHERE gr.player_id = ?
               ORDER BY gr.recorded_at DESC
               LIMIT ?""",
            (player_id, limit)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def update_push_notifications(telegram_id: int, enabled: bool):
    async with await get_db() as db:
        await db.execute(
            "UPDATE players SET push_notifications=? WHERE telegram_id=?",
            (1 if enabled else 0, telegram_id)
        )
        await db.commit()


async def get_all_players_for_broadcast() -> list:
    async with await get_db() as db:
        cursor = await db.execute(
            "SELECT telegram_id FROM players WHERE push_notifications = 1"
        )
        rows = await cursor.fetchall()
        return [r[0] for r in rows]
