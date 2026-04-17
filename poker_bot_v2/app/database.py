import aiosqlite
from typing import Optional, List, Dict
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
                username         TEXT    DEFAULT '',
                tg_name          TEXT    DEFAULT '',
                fio              TEXT    DEFAULT '',
                phone            TEXT    DEFAULT '',
                city             TEXT    DEFAULT '',
                rating           REAL    DEFAULT 0.0,
                pro_score        REAL    DEFAULT 0.0,
                knockouts        INTEGER DEFAULT 0,
                games_count      INTEGER DEFAULT 0,
                wins_count       INTEGER DEFAULT 0,
                best_place       INTEGER DEFAULT 0,
                profile_complete INTEGER DEFAULT 0,
                created_at       TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS tournaments (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                title        TEXT NOT NULL,
                description  TEXT DEFAULT '',
                location     TEXT DEFAULT '',
                city         TEXT DEFAULT 'Москва',
                start_time   TEXT NOT NULL,
                max_players  INTEGER DEFAULT 100,
                buy_in       INTEGER DEFAULT 0,
                prize_pool   TEXT    DEFAULT '',
                status       TEXT    DEFAULT 'upcoming',
                created_at   TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS registrations (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL REFERENCES tournaments(id),
                player_id     INTEGER NOT NULL REFERENCES players(id),
                status        TEXT DEFAULT 'registered',
                registered_at TEXT DEFAULT (datetime('now')),
                UNIQUE(tournament_id, player_id)
            );

            CREATE TABLE IF NOT EXISTS game_results (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL REFERENCES tournaments(id),
                player_id     INTEGER NOT NULL REFERENCES players(id),
                place         INTEGER DEFAULT 0,
                knockouts     INTEGER DEFAULT 0,
                prize         REAL    DEFAULT 0.0,
                rating_delta  REAL    DEFAULT 0.0,
                pro_delta     REAL    DEFAULT 0.0,
                recorded_at   TEXT    DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_players_tg   ON players(tg_id);
            CREATE INDEX IF NOT EXISTS idx_reg_tour     ON registrations(tournament_id);
            CREATE INDEX IF NOT EXISTS idx_reg_player   ON registrations(player_id);
            CREATE INDEX IF NOT EXISTS idx_res_tour     ON game_results(tournament_id);
            CREATE INDEX IF NOT EXISTS idx_res_player   ON game_results(player_id);
        """)
        await db.commit()

    # Safe migration for existing DBs
    _new_cols = [
        ("fio",              "TEXT DEFAULT ''"),
        ("phone",            "TEXT DEFAULT ''"),
        ("city",             "TEXT DEFAULT ''"),
        ("tg_name",          "TEXT DEFAULT ''"),
        ("best_place",       "INTEGER DEFAULT 0"),
        ("profile_complete", "INTEGER DEFAULT 0"),
        ("pro_score",        "REAL DEFAULT 0.0"),
        ("knockouts",        "INTEGER DEFAULT 0"),
        ("games_count",      "INTEGER DEFAULT 0"),
        ("wins_count",       "INTEGER DEFAULT 0"),
    ]
    async with aiosqlite.connect(DB_PATH) as db:
        for col, col_def in _new_cols:
            try:
                await db.execute(f"ALTER TABLE players ADD COLUMN {col} {col_def}")
                await db.commit()
            except Exception:
                pass


# ─── PLAYERS ────────────────────────────────────────────────────────────────

async def get_or_create_player(tg_id: int, username: str, tg_name: str) -> Dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await db.execute("SELECT * FROM players WHERE tg_id=?", (tg_id,))
        p = await row.fetchone()
        if p:
            await db.execute(
                "UPDATE players SET username=?, tg_name=? WHERE tg_id=?",
                (username, tg_name, tg_id)
            )
            await db.commit()
            row = await db.execute("SELECT * FROM players WHERE tg_id=?", (tg_id,))
            return dict(await row.fetchone())
        await db.execute(
            "INSERT INTO players (tg_id, username, tg_name) VALUES (?,?,?)",
            (tg_id, username, tg_name)
        )
        await db.commit()
        row = await db.execute("SELECT * FROM players WHERE tg_id=?", (tg_id,))
        return dict(await row.fetchone())


async def complete_profile(tg_id: int, fio: str, phone: str, city: str) -> Dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            """UPDATE players SET fio=?, phone=?, city=?, profile_complete=1
               WHERE tg_id=?""",
            (fio.strip(), phone.strip(), city.strip(), tg_id)
        )
        await db.commit()
        row = await db.execute("SELECT * FROM players WHERE tg_id=?", (tg_id,))
        return dict(await row.fetchone())


async def get_player_by_tg(tg_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await db.execute("SELECT * FROM players WHERE tg_id=?", (tg_id,))
        p = await row.fetchone()
        return dict(p) if p else None


async def get_player_by_id(player_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await db.execute("SELECT * FROM players WHERE id=?", (player_id,))
        p = await row.fetchone()
        return dict(p) if p else None


async def get_all_players(search: str = "") -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if search:
            rows = await db.execute(
                """SELECT * FROM players
                   WHERE fio LIKE ? OR username LIKE ? OR phone LIKE ?
                   ORDER BY rating DESC LIMIT 200""",
                (f"%{search}%", f"%{search}%", f"%{search}%")
            )
        else:
            rows = await db.execute(
                "SELECT * FROM players ORDER BY rating DESC LIMIT 200"
            )
        return [dict(r) for r in await rows.fetchall()]


async def get_leaderboard(city: str = "") -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if city:
            rows = await db.execute(
                """SELECT * FROM players
                   WHERE profile_complete=1 AND city=?
                   ORDER BY rating DESC LIMIT 100""",
                (city,)
            )
        else:
            rows = await db.execute(
                """SELECT * FROM players
                   WHERE profile_complete=1
                   ORDER BY rating DESC LIMIT 100"""
            )
        return [dict(r) for r in await rows.fetchall()]


async def get_admin_stats() -> Dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        def q(sql, *args):
            return db.execute(sql, args)

        r = await (await q("SELECT COUNT(*) c FROM players")).fetchone()
        total = r["c"]
        r = await (await q("SELECT COUNT(*) c FROM players WHERE profile_complete=1")).fetchone()
        active = r["c"]
        r = await (await q("SELECT COUNT(*) c FROM tournaments WHERE status='upcoming'")).fetchone()
        upcoming = r["c"]
        r = await (await q("SELECT COUNT(*) c FROM registrations WHERE status='registered'")).fetchone()
        regs = r["c"]

        return {
            "total_players": total,
            "active_players": active,
            "upcoming_tournaments": upcoming,
            "total_registrations": regs,
        }


async def admin_update_player(player_id: int, fields: Dict) -> Dict:
    allowed = {"fio", "phone", "city", "rating", "pro_score", "knockouts",
               "games_count", "wins_count", "best_place"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return await get_player_by_id(player_id) or {}
    clause = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [player_id]
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(f"UPDATE players SET {clause} WHERE id=?", vals)
        await db.commit()
        row = await db.execute("SELECT * FROM players WHERE id=?", (player_id,))
        return dict(await row.fetchone())


# ─── TOURNAMENTS ────────────────────────────────────────────────────────────

async def get_tournaments(status: str = "upcoming", city: str = "") -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if city:
            rows = await db.execute(
                """SELECT t.*, COUNT(r.id) AS registered_count
                   FROM tournaments t
                   LEFT JOIN registrations r ON r.tournament_id=t.id AND r.status='registered'
                   WHERE t.status=? AND t.city=?
                   GROUP BY t.id ORDER BY t.start_time ASC""",
                (status, city)
            )
        else:
            rows = await db.execute(
                """SELECT t.*, COUNT(r.id) AS registered_count
                   FROM tournaments t
                   LEFT JOIN registrations r ON r.tournament_id=t.id AND r.status='registered'
                   WHERE t.status=?
                   GROUP BY t.id ORDER BY t.start_time ASC""",
                (status,)
            )
        return [dict(r) for r in await rows.fetchall()]


async def get_tournament(tid: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await db.execute(
            """SELECT t.*, COUNT(r.id) AS registered_count
               FROM tournaments t
               LEFT JOIN registrations r ON r.tournament_id=t.id AND r.status='registered'
               WHERE t.id=? GROUP BY t.id""",
            (tid,)
        )
        t = await row.fetchone()
        return dict(t) if t else None


async def create_tournament(data: Dict) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO tournaments
               (title, description, location, city, start_time, max_players, buy_in, prize_pool)
               VALUES (?,?,?,?,?,?,?,?)""",
            (data.get("title", ""), data.get("description", ""),
             data.get("location", ""), data.get("city", "Москва"),
             data["start_time"], data.get("max_players", 100),
             data.get("buy_in", 0), data.get("prize_pool", ""))
        )
        await db.commit()
        return cur.lastrowid


async def update_tournament_status(tid: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE tournaments SET status=? WHERE id=?", (status, tid))
        await db.commit()


async def delete_tournament(tid: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM registrations WHERE tournament_id=?", (tid,))
        await db.execute("DELETE FROM game_results WHERE tournament_id=?", (tid,))
        await db.execute("DELETE FROM tournaments WHERE id=?", (tid,))
        await db.commit()


# ─── REGISTRATIONS ──────────────────────────────────────────────────────────

async def register_player(tid: int, player_id: int) -> Dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await db.execute(
            "SELECT * FROM registrations WHERE tournament_id=? AND player_id=?",
            (tid, player_id)
        )
        existing = await row.fetchone()
        if existing:
            ex = dict(existing)
            if ex["status"] == "cancelled":
                await db.execute(
                    "UPDATE registrations SET status='registered', registered_at=datetime('now') WHERE tournament_id=? AND player_id=?",
                    (tid, player_id)
                )
                await db.commit()
                return {"ok": True}
            return {"ok": False, "reason": "already_registered"}

        row = await db.execute(
            """SELECT t.max_players, COUNT(r.id) AS cnt
               FROM tournaments t
               LEFT JOIN registrations r ON r.tournament_id=t.id AND r.status='registered'
               WHERE t.id=?""",
            (tid,)
        )
        t = dict(await row.fetchone())
        if t["cnt"] >= t["max_players"]:
            return {"ok": False, "reason": "full"}

        await db.execute(
            "INSERT INTO registrations (tournament_id, player_id) VALUES (?,?)",
            (tid, player_id)
        )
        await db.commit()
        return {"ok": True}


async def unregister_player(tid: int, player_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE registrations SET status='cancelled' WHERE tournament_id=? AND player_id=?",
            (tid, player_id)
        )
        await db.commit()


async def is_registered(tid: int, player_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute(
            "SELECT 1 FROM registrations WHERE tournament_id=? AND player_id=? AND status='registered'",
            (tid, player_id)
        )
        return bool(await row.fetchone())


async def get_participants(tid: int) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute(
            """SELECT p.id, p.tg_id, p.fio, p.username, p.city, p.rating,
                      p.wins_count, p.knockouts, r.registered_at
               FROM registrations r
               JOIN players p ON p.id=r.player_id
               WHERE r.tournament_id=? AND r.status='registered'
               ORDER BY r.registered_at ASC""",
            (tid,)
        )
        return [dict(r) for r in await rows.fetchall()]


async def get_my_tournaments(player_id: int) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute(
            """SELECT t.id, t.title, t.start_time, t.status, t.city,
                      r.status AS reg_status, r.registered_at,
                      gr.place, gr.knockouts, gr.rating_delta, gr.pro_delta, gr.prize
               FROM registrations r
               JOIN tournaments t ON t.id=r.tournament_id
               LEFT JOIN game_results gr ON gr.tournament_id=t.id AND gr.player_id=r.player_id
               WHERE r.player_id=?
               ORDER BY t.start_time DESC""",
            (player_id,)
        )
        return [dict(r) for r in await rows.fetchall()]


# ─── RESULTS ────────────────────────────────────────────────────────────────

async def record_result(tid: int, player_id: int, place: int,
                        knockouts: int = 0, prize: float = 0.0):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await db.execute("SELECT max_players FROM tournaments WHERE id=?", (tid,))
        t = await row.fetchone()
        max_p = t["max_players"] if t else 100

        # Rating formula: more players = more points; 1st place gets max
        rating_delta = max(0, (max_p - place + 1) * 10) + knockouts * 5
        pro_delta    = knockouts * 25.0

        await db.execute(
            """INSERT OR REPLACE INTO game_results
               (tournament_id, player_id, place, knockouts, prize, rating_delta, pro_delta)
               VALUES (?,?,?,?,?,?,?)""",
            (tid, player_id, place, knockouts, prize, rating_delta, pro_delta)
        )
        # Update player stats
        row = await db.execute(
            "SELECT best_place FROM players WHERE id=?", (player_id,)
        )
        p = await row.fetchone()
        best = p["best_place"] if p and p["best_place"] else place
        new_best = min(best, place) if best else place

        await db.execute(
            """UPDATE players SET
               rating      = rating + ?,
               pro_score   = pro_score + ?,
               knockouts   = knockouts + ?,
               games_count = games_count + 1,
               wins_count  = wins_count + ?,
               best_place  = ?
               WHERE id=?""",
            (rating_delta, pro_delta, knockouts,
             1 if place == 1 else 0, new_best, player_id)
        )
        await db.execute(
            "UPDATE registrations SET status='finished' WHERE tournament_id=? AND player_id=?",
            (tid, player_id)
        )
        await db.commit()
