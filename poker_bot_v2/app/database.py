import aiosqlite
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

DB_PATH = Path("data/poker_bot.db")


async def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS players (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id            INTEGER UNIQUE NOT NULL,
                username         TEXT,
                full_name        TEXT NOT NULL,
                game_nickname    TEXT,
                email            TEXT,
                birth_date       TEXT,
                referral_code    TEXT,
                photo_url        TEXT,
                city             TEXT DEFAULT 'Не указан',
                rating           REAL DEFAULT 0.0,
                pro_score        REAL DEFAULT 0.0,
                knockouts        INTEGER DEFAULT 0,
                free_entry       INTEGER DEFAULT 0,
                games_count      INTEGER DEFAULT 0,
                wins_count       INTEGER DEFAULT 0,
                push_notify      INTEGER DEFAULT 1,
                profile_complete INTEGER DEFAULT 0,
                created_at       TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS tournaments (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                title        TEXT NOT NULL,
                description  TEXT,
                rules        TEXT,
                location     TEXT,
                address      TEXT,
                city         TEXT DEFAULT 'Москва',
                start_time   TEXT NOT NULL,
                max_players  INTEGER DEFAULT 100,
                buy_in       INTEGER DEFAULT 0,
                prize_pool   TEXT,
                status       TEXT DEFAULT 'upcoming',
                banner_url   TEXT,
                created_at   TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS registrations (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id   INTEGER NOT NULL REFERENCES tournaments(id),
                player_id       INTEGER NOT NULL REFERENCES players(id),
                seat_number     INTEGER,
                status          TEXT DEFAULT 'registered',
                registered_at   TEXT DEFAULT (datetime('now')),
                UNIQUE(tournament_id, player_id)
            );

            CREATE TABLE IF NOT EXISTS game_results (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id   INTEGER NOT NULL REFERENCES tournaments(id),
                player_id       INTEGER NOT NULL REFERENCES players(id),
                place           INTEGER,
                knockouts       INTEGER DEFAULT 0,
                prize           REAL DEFAULT 0.0,
                rating_delta    REAL DEFAULT 0.0,
                pro_delta       REAL DEFAULT 0.0,
                recorded_at     TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS bookings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id   INTEGER NOT NULL REFERENCES players(id),
                date        TEXT NOT NULL,
                time_slot   TEXT NOT NULL,
                seats       INTEGER DEFAULT 1,
                note        TEXT,
                status      TEXT DEFAULT 'pending',
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_players_tg_id     ON players(tg_id);
            CREATE INDEX IF NOT EXISTS idx_reg_tournament     ON registrations(tournament_id);
            CREATE INDEX IF NOT EXISTS idx_reg_player         ON registrations(player_id);
            CREATE INDEX IF NOT EXISTS idx_results_tournament ON game_results(tournament_id);
            CREATE INDEX IF NOT EXISTS idx_results_player     ON game_results(player_id);
        """)
        await db.commit()

    # Safe migration for existing databases
    _migration_columns = [
        ("game_nickname",    "TEXT"),
        ("email",            "TEXT"),
        ("birth_date",       "TEXT"),
        ("referral_code",    "TEXT"),
        ("photo_url",        "TEXT"),
        ("profile_complete", "INTEGER DEFAULT 0"),
    ]
    async with aiosqlite.connect(DB_PATH) as db:
        for col, col_type in _migration_columns:
            try:
                await db.execute(f"ALTER TABLE players ADD COLUMN {col} {col_type}")
                await db.commit()
            except Exception:
                pass  # column already exists


async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


# ─── PLAYERS ────────────────────────────────────────────────────────────────

async def get_or_create_player(tg_id: int, username: str, full_name: str) -> Dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await db.execute("SELECT * FROM players WHERE tg_id = ?", (tg_id,))
        player = await row.fetchone()
        if player:
            await db.execute(
                "UPDATE players SET username=?, full_name=? WHERE tg_id=?",
                (username, full_name, tg_id)
            )
            await db.commit()
            row = await db.execute("SELECT * FROM players WHERE tg_id = ?", (tg_id,))
            return dict(await row.fetchone())
        await db.execute(
            "INSERT INTO players (tg_id, username, full_name) VALUES (?,?,?)",
            (tg_id, username, full_name)
        )
        await db.commit()
        row = await db.execute("SELECT * FROM players WHERE tg_id = ?", (tg_id,))
        return dict(await row.fetchone())


async def get_player_by_tg(tg_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await db.execute("SELECT * FROM players WHERE tg_id = ?", (tg_id,))
        p = await row.fetchone()
        return dict(p) if p else None


async def get_player_by_id(player_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await db.execute("SELECT * FROM players WHERE id = ?", (player_id,))
        p = await row.fetchone()
        return dict(p) if p else None


async def complete_player_profile(
    tg_id: int,
    game_nickname: str,
    email: Optional[str] = None,
    birth_date: Optional[str] = None,
    referral_code: Optional[str] = None,
    photo_url: Optional[str] = None,
) -> Dict:
    """Mark profile as complete and save extended fields."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Ensure player row exists
        row = await db.execute("SELECT id FROM players WHERE tg_id=?", (tg_id,))
        existing = await row.fetchone()
        if not existing:
            return {}
        await db.execute(
            """UPDATE players SET
                game_nickname=?, email=?, birth_date=?,
                referral_code=?, photo_url=?, profile_complete=1
               WHERE tg_id=?""",
            (game_nickname, email or None, birth_date or None,
             referral_code or None, photo_url or None, tg_id)
        )
        await db.commit()
        row = await db.execute("SELECT * FROM players WHERE tg_id=?", (tg_id,))
        return dict(await row.fetchone())


async def update_player_profile(tg_id: int, fields: Dict) -> Dict:
    """Update arbitrary allowed profile fields."""
    allowed = {"game_nickname", "email", "birth_date", "city", "photo_url", "push_notify"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return await get_player_by_tg(tg_id) or {}
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [tg_id]
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(f"UPDATE players SET {set_clause} WHERE tg_id=?", values)
        await db.commit()
        row = await db.execute("SELECT * FROM players WHERE tg_id=?", (tg_id,))
        return dict(await row.fetchone())


async def get_all_players(search: str = "", limit: int = 200) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if search:
            rows = await db.execute(
                """SELECT * FROM players
                   WHERE full_name LIKE ? OR username LIKE ? OR game_nickname LIKE ?
                   ORDER BY rating DESC LIMIT ?""",
                (f"%{search}%", f"%{search}%", f"%{search}%", limit)
            )
        else:
            rows = await db.execute(
                "SELECT * FROM players ORDER BY rating DESC LIMIT ?", (limit,)
            )
        return [dict(r) for r in await rows.fetchall()]


async def get_leaderboard(season: bool = False, limit: int = 50) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        order = "rating DESC" if not season else "pro_score DESC"
        rows = await db.execute(
            f"SELECT * FROM players ORDER BY {order} LIMIT ?", (limit,)
        )
        return [dict(r) for r in await rows.fetchall()]


async def update_player_city(tg_id: int, city: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE players SET city=? WHERE tg_id=?", (city, tg_id))
        await db.commit()


async def admin_update_player(player_id: int, fields: Dict) -> Dict:
    """Admin: update any player fields including rating."""
    allowed = {"game_nickname", "email", "city", "rating", "pro_score",
               "knockouts", "games_count", "wins_count", "free_entry"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return await get_player_by_id(player_id) or {}
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [player_id]
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(f"UPDATE players SET {set_clause} WHERE id=?", values)
        await db.commit()
        row = await db.execute("SELECT * FROM players WHERE id=?", (player_id,))
        return dict(await row.fetchone())


# ─── TOURNAMENTS ────────────────────────────────────────────────────────────

async def get_tournaments(status: str = "upcoming") -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute(
            """SELECT t.*,
                      COUNT(r.id) as registered_count
               FROM tournaments t
               LEFT JOIN registrations r ON r.tournament_id = t.id AND r.status='registered'
               WHERE t.status = ?
               GROUP BY t.id
               ORDER BY t.start_time ASC""",
            (status,)
        )
        return [dict(r) for r in await rows.fetchall()]


async def get_tournament(tournament_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await db.execute(
            """SELECT t.*,
                      COUNT(r.id) as registered_count
               FROM tournaments t
               LEFT JOIN registrations r ON r.tournament_id = t.id AND r.status='registered'
               WHERE t.id = ?
               GROUP BY t.id""",
            (tournament_id,)
        )
        t = await row.fetchone()
        return dict(t) if t else None


async def create_tournament(data: Dict) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO tournaments
               (title, description, rules, location, address, city,
                start_time, max_players, buy_in, prize_pool, banner_url)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (data.get("title"), data.get("description"), data.get("rules"),
             data.get("location"), data.get("address"), data.get("city", "Москва"),
             data["start_time"], data.get("max_players", 100),
             data.get("buy_in", 0), data.get("prize_pool"), data.get("banner_url"))
        )
        await db.commit()
        return cur.lastrowid


async def update_tournament(tournament_id: int, data: Dict):
    allowed = {"title", "description", "rules", "location", "address", "city",
               "start_time", "max_players", "buy_in", "prize_pool", "banner_url", "status"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [tournament_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE tournaments SET {set_clause} WHERE id=?", values)
        await db.commit()


async def update_tournament_status(tournament_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tournaments SET status=? WHERE id=?", (status, tournament_id)
        )
        await db.commit()


async def delete_tournament(tournament_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM registrations WHERE tournament_id=?", (tournament_id,))
        await db.execute("DELETE FROM game_results WHERE tournament_id=?", (tournament_id,))
        await db.execute("DELETE FROM tournaments WHERE id=?", (tournament_id,))
        await db.commit()


# ─── REGISTRATIONS ──────────────────────────────────────────────────────────

async def register_player(tournament_id: int, player_id: int) -> Dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await db.execute(
            "SELECT * FROM registrations WHERE tournament_id=? AND player_id=?",
            (tournament_id, player_id)
        )
        existing = await row.fetchone()
        if existing:
            if dict(existing)["status"] == "cancelled":
                await db.execute(
                    "UPDATE registrations SET status='registered', registered_at=datetime('now') WHERE tournament_id=? AND player_id=?",
                    (tournament_id, player_id)
                )
                await db.commit()
                return {"ok": True}
            return {"ok": False, "reason": "already_registered"}

        t_row = await db.execute(
            """SELECT max_players, COUNT(r.id) as cnt
               FROM tournaments t
               LEFT JOIN registrations r ON r.tournament_id=t.id AND r.status='registered'
               WHERE t.id=?""", (tournament_id,)
        )
        t = await t_row.fetchone()
        if t and t["cnt"] >= t["max_players"]:
            return {"ok": False, "reason": "full"}

        await db.execute(
            "INSERT INTO registrations (tournament_id, player_id) VALUES (?,?)",
            (tournament_id, player_id)
        )
        await db.commit()
        return {"ok": True}


async def unregister_player(tournament_id: int, player_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE registrations SET status='cancelled' WHERE tournament_id=? AND player_id=?",
            (tournament_id, player_id)
        )
        await db.commit()
        return True


async def is_registered(tournament_id: int, player_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute(
            "SELECT 1 FROM registrations WHERE tournament_id=? AND player_id=? AND status='registered'",
            (tournament_id, player_id)
        )
        return bool(await row.fetchone())


async def get_tournament_participants(tournament_id: int) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute(
            """SELECT p.id, p.tg_id, p.username, p.full_name, p.game_nickname,
                      p.photo_url, p.rating, p.wins_count, p.games_count,
                      r.registered_at, r.seat_number
               FROM registrations r
               JOIN players p ON p.id = r.player_id
               WHERE r.tournament_id=? AND r.status='registered'
               ORDER BY r.registered_at ASC""",
            (tournament_id,)
        )
        return [dict(r) for r in await rows.fetchall()]


async def get_player_tournaments(player_id: int) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute(
            """SELECT t.*, r.registered_at, r.status as reg_status,
                      gr.place, gr.knockouts, gr.rating_delta
               FROM registrations r
               JOIN tournaments t ON t.id = r.tournament_id
               LEFT JOIN game_results gr ON gr.tournament_id=t.id AND gr.player_id=r.player_id
               WHERE r.player_id=?
               ORDER BY t.start_time DESC""",
            (player_id,)
        )
        return [dict(r) for r in await rows.fetchall()]


# ─── GAME RESULTS ───────────────────────────────────────────────────────────

async def record_result(tournament_id: int, player_id: int,
                        place: int, knockouts: int = 0,
                        prize: float = 0.0):
    """Record result and recalculate rating."""
    max_pl_row = None
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        r = await db.execute(
            "SELECT max_players FROM tournaments WHERE id=?", (tournament_id,)
        )
        max_pl_row = await r.fetchone()

    max_players = max_pl_row["max_players"] if max_pl_row else 100
    rating_delta = max(0, (max_players - place + 1) * 10) + knockouts * 5
    pro_delta = knockouts * 25.0

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR REPLACE INTO game_results
               (tournament_id, player_id, place, knockouts, prize, rating_delta, pro_delta)
               VALUES (?,?,?,?,?,?,?)""",
            (tournament_id, player_id, place, knockouts, prize, rating_delta, pro_delta)
        )
        await db.execute(
            """UPDATE players SET
               rating      = rating + ?,
               pro_score   = pro_score + ?,
               knockouts   = knockouts + ?,
               games_count = games_count + 1,
               wins_count  = wins_count + ?
               WHERE id=?""",
            (rating_delta, pro_delta, knockouts, 1 if place == 1 else 0, player_id)
        )
        await db.execute(
            "UPDATE registrations SET status='finished' WHERE tournament_id=? AND player_id=?",
            (tournament_id, player_id)
        )
        await db.commit()


async def get_admin_stats() -> Dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        r = await db.execute("SELECT COUNT(*) as cnt FROM players")
        total_players = (await r.fetchone())["cnt"]

        r = await db.execute("SELECT COUNT(*) as cnt FROM players WHERE profile_complete=1")
        active_players = (await r.fetchone())["cnt"]

        r = await db.execute("SELECT COUNT(*) as cnt FROM tournaments WHERE status='upcoming'")
        upcoming_tours = (await r.fetchone())["cnt"]

        r = await db.execute("SELECT COUNT(*) as cnt FROM tournaments WHERE status='finished'")
        finished_tours = (await r.fetchone())["cnt"]

        r = await db.execute("SELECT COUNT(*) as cnt FROM registrations WHERE status='registered'")
        total_regs = (await r.fetchone())["cnt"]

        r = await db.execute("SELECT COUNT(*) as cnt FROM bookings WHERE status='pending'")
        pending_bookings = (await r.fetchone())["cnt"]

        return {
            "total_players": total_players,
            "active_players": active_players,
            "upcoming_tournaments": upcoming_tours,
            "finished_tournaments": finished_tours,
            "total_registrations": total_regs,
            "pending_bookings": pending_bookings,
        }


# ─── BOOKINGS ───────────────────────────────────────────────────────────────

async def create_booking(player_id: int, date: str, time_slot: str,
                         seats: int = 1, note: str = "") -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO bookings (player_id, date, time_slot, seats, note) VALUES (?,?,?,?,?)",
            (player_id, date, time_slot, seats, note)
        )
        await db.commit()
        return cur.lastrowid


async def get_player_bookings(player_id: int) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute(
            "SELECT * FROM bookings WHERE player_id=? ORDER BY date DESC, time_slot DESC",
            (player_id,)
        )
        return [dict(r) for r in await rows.fetchall()]


async def get_all_bookings(status: str = "pending") -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute(
            """SELECT b.*, p.full_name, p.username, p.tg_id, p.game_nickname
               FROM bookings b JOIN players p ON p.id=b.player_id
               WHERE b.status=? ORDER BY b.date ASC, b.time_slot ASC""",
            (status,)
        )
        return [dict(r) for r in await rows.fetchall()]


async def update_booking_status(booking_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE bookings SET status=? WHERE id=?", (status, booking_id)
        )
        await db.commit()
