"""
Async PostgreSQL database layer (asyncpg).
Connection string is read from DATABASE_URL env-var (set on Render).
"""
import os
import asyncpg
from typing import Optional, List, Dict

_pool: Optional[asyncpg.Pool] = None


def _row(record) -> Dict:
    """Convert asyncpg.Record → plain dict."""
    return dict(record) if record else {}


async def _get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        raise RuntimeError("DB pool not initialised — call init_db() first")
    return _pool


# ─── INIT ────────────────────────────────────────────────────────────────────

async def init_db():
    global _pool
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise ValueError("DATABASE_URL environment variable is not set")

    # Render gives postgres:// — asyncpg needs postgresql://
    url = url.replace("postgres://", "postgresql://", 1)

    _pool = await asyncpg.create_pool(url, min_size=1, max_size=5,
                                      ssl="require")

    async with _pool.acquire() as c:
        await c.execute("""
            CREATE TABLE IF NOT EXISTS players (
                id               SERIAL PRIMARY KEY,
                tg_id            BIGINT  UNIQUE NOT NULL,
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
                created_at       TEXT    DEFAULT (NOW()::TEXT)
            )
        """)
        await c.execute("""
            CREATE TABLE IF NOT EXISTS tournaments (
                id           SERIAL PRIMARY KEY,
                title        TEXT    NOT NULL,
                description  TEXT    DEFAULT '',
                location     TEXT    DEFAULT '',
                city         TEXT    DEFAULT 'Москва',
                start_time   TEXT    NOT NULL,
                max_players  INTEGER DEFAULT 100,
                buy_in       INTEGER DEFAULT 0,
                prize_pool   TEXT    DEFAULT '',
                status       TEXT    DEFAULT 'upcoming',
                created_at   TEXT    DEFAULT (NOW()::TEXT)
            )
        """)
        await c.execute("""
            CREATE TABLE IF NOT EXISTS registrations (
                id            SERIAL PRIMARY KEY,
                tournament_id INTEGER NOT NULL REFERENCES tournaments(id),
                player_id     INTEGER NOT NULL REFERENCES players(id),
                status        TEXT    DEFAULT 'registered',
                registered_at TEXT    DEFAULT (NOW()::TEXT),
                UNIQUE(tournament_id, player_id)
            )
        """)
        await c.execute("""
            CREATE TABLE IF NOT EXISTS game_results (
                id            SERIAL PRIMARY KEY,
                tournament_id INTEGER NOT NULL REFERENCES tournaments(id),
                player_id     INTEGER NOT NULL REFERENCES players(id),
                place         INTEGER DEFAULT 0,
                knockouts     INTEGER DEFAULT 0,
                prize         REAL    DEFAULT 0.0,
                rating_delta  REAL    DEFAULT 0.0,
                pro_delta     REAL    DEFAULT 0.0,
                recorded_at   TEXT    DEFAULT (NOW()::TEXT),
                UNIQUE(tournament_id, player_id)
            )
        """)
        for sql in [
            "CREATE INDEX IF NOT EXISTS idx_players_tg  ON players(tg_id)",
            "CREATE INDEX IF NOT EXISTS idx_reg_tour    ON registrations(tournament_id)",
            "CREATE INDEX IF NOT EXISTS idx_reg_player  ON registrations(player_id)",
            "CREATE INDEX IF NOT EXISTS idx_res_tour    ON game_results(tournament_id)",
            "CREATE INDEX IF NOT EXISTS idx_res_player  ON game_results(player_id)",
            # Migrations for existing databases
            "ALTER TABLE tournaments   ADD COLUMN IF NOT EXISTS table_count  INTEGER DEFAULT 0",
            "ALTER TABLE registrations ADD COLUMN IF NOT EXISTS table_number INTEGER DEFAULT 0",
        ]:
            await c.execute(sql)


# ─── PLAYERS ─────────────────────────────────────────────────────────────────

async def get_or_create_player(tg_id: int, username: str, tg_name: str) -> Dict:
    pool = await _get_pool()
    async with pool.acquire() as c:
        row = await c.fetchrow("SELECT * FROM players WHERE tg_id=$1", tg_id)
        if row:
            await c.execute(
                "UPDATE players SET username=$1, tg_name=$2 WHERE tg_id=$3",
                username, tg_name, tg_id
            )
            row = await c.fetchrow("SELECT * FROM players WHERE tg_id=$1", tg_id)
            return _row(row)
        await c.execute(
            "INSERT INTO players (tg_id, username, tg_name) VALUES ($1,$2,$3)",
            tg_id, username, tg_name
        )
        row = await c.fetchrow("SELECT * FROM players WHERE tg_id=$1", tg_id)
        return _row(row)


async def complete_profile(tg_id: int, fio: str, phone: str, city: str) -> Dict:
    pool = await _get_pool()
    async with pool.acquire() as c:
        await c.execute(
            """UPDATE players SET fio=$1, phone=$2, city=$3, profile_complete=1
               WHERE tg_id=$4""",
            fio.strip(), phone.strip(), city.strip(), tg_id
        )
        row = await c.fetchrow("SELECT * FROM players WHERE tg_id=$1", tg_id)
        return _row(row)


async def get_player_by_tg(tg_id: int) -> Optional[Dict]:
    pool = await _get_pool()
    async with pool.acquire() as c:
        row = await c.fetchrow("SELECT * FROM players WHERE tg_id=$1", tg_id)
        return _row(row) if row else None


async def get_player_by_id(player_id: int) -> Optional[Dict]:
    pool = await _get_pool()
    async with pool.acquire() as c:
        row = await c.fetchrow("SELECT * FROM players WHERE id=$1", player_id)
        return _row(row) if row else None


async def get_all_players(search: str = "") -> List[Dict]:
    pool = await _get_pool()
    async with pool.acquire() as c:
        if search:
            pat = f"%{search}%"
            rows = await c.fetch(
                """SELECT * FROM players
                   WHERE fio ILIKE $1 OR username ILIKE $1 OR phone ILIKE $1
                   ORDER BY rating DESC LIMIT 200""",
                pat
            )
        else:
            rows = await c.fetch(
                "SELECT * FROM players ORDER BY rating DESC LIMIT 200"
            )
        return [_row(r) for r in rows]


async def get_leaderboard(city: str = "") -> List[Dict]:
    pool = await _get_pool()
    async with pool.acquire() as c:
        if city:
            rows = await c.fetch(
                """SELECT * FROM players
                   WHERE profile_complete=1 AND city=$1
                   ORDER BY rating DESC LIMIT 100""",
                city
            )
        else:
            rows = await c.fetch(
                """SELECT * FROM players
                   WHERE profile_complete=1
                   ORDER BY rating DESC LIMIT 100"""
            )
        return [_row(r) for r in rows]


async def get_admin_stats() -> Dict:
    pool = await _get_pool()
    async with pool.acquire() as c:
        total    = (await c.fetchrow("SELECT COUNT(*) AS c FROM players"))["c"]
        active   = (await c.fetchrow("SELECT COUNT(*) AS c FROM players WHERE profile_complete=1"))["c"]
        upcoming = (await c.fetchrow("SELECT COUNT(*) AS c FROM tournaments WHERE status='upcoming'"))["c"]
        regs     = (await c.fetchrow("SELECT COUNT(*) AS c FROM registrations WHERE status='registered'"))["c"]
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
    keys = list(updates.keys())
    vals = list(updates.values())
    clause = ", ".join(f"{k}=${i+1}" for i, k in enumerate(keys))
    vals.append(player_id)
    pool = await _get_pool()
    async with pool.acquire() as c:
        await c.execute(
            f"UPDATE players SET {clause} WHERE id=${len(vals)}",
            *vals
        )
        row = await c.fetchrow("SELECT * FROM players WHERE id=$1", player_id)
        return _row(row)


# ─── TOURNAMENTS ──────────────────────────────────────────────────────────────

async def get_tournaments(status: str = "upcoming", city: str = "") -> List[Dict]:
    pool = await _get_pool()
    async with pool.acquire() as c:
        if city:
            rows = await c.fetch(
                """SELECT t.*, COUNT(r.id) AS registered_count
                   FROM tournaments t
                   LEFT JOIN registrations r
                          ON r.tournament_id=t.id AND r.status='registered'
                   WHERE t.status=$1 AND t.city=$2
                   GROUP BY t.id ORDER BY t.start_time ASC""",
                status, city
            )
        else:
            rows = await c.fetch(
                """SELECT t.*, COUNT(r.id) AS registered_count
                   FROM tournaments t
                   LEFT JOIN registrations r
                          ON r.tournament_id=t.id AND r.status='registered'
                   WHERE t.status=$1
                   GROUP BY t.id ORDER BY t.start_time ASC""",
                status
            )
        return [_row(r) for r in rows]


async def get_tournament(tid: int) -> Optional[Dict]:
    pool = await _get_pool()
    async with pool.acquire() as c:
        row = await c.fetchrow(
            """SELECT t.*, COUNT(r.id) AS registered_count
               FROM tournaments t
               LEFT JOIN registrations r
                      ON r.tournament_id=t.id AND r.status='registered'
               WHERE t.id=$1 GROUP BY t.id""",
            tid
        )
        return _row(row) if row else None


async def create_tournament(data: Dict) -> int:
    pool = await _get_pool()
    async with pool.acquire() as c:
        row = await c.fetchrow(
            """INSERT INTO tournaments
               (title, description, location, city, start_time,
                max_players, buy_in, prize_pool, table_count)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING id""",
            data.get("title", ""), data.get("description", ""),
            data.get("location", ""), data.get("city", "Москва"),
            data["start_time"], data.get("max_players", 100),
            data.get("buy_in", 0), data.get("prize_pool", ""),
            int(data.get("table_count", 0)),
        )
        return row["id"]


async def update_tournament_status(tid: int, status: str):
    pool = await _get_pool()
    async with pool.acquire() as c:
        await c.execute("UPDATE tournaments SET status=$1 WHERE id=$2", status, tid)


async def delete_tournament(tid: int):
    pool = await _get_pool()
    async with pool.acquire() as c:
        await c.execute("DELETE FROM registrations WHERE tournament_id=$1", tid)
        await c.execute("DELETE FROM game_results  WHERE tournament_id=$1", tid)
        await c.execute("DELETE FROM tournaments   WHERE id=$1", tid)


# ─── REGISTRATIONS ───────────────────────────────────────────────────────────

async def register_player(tid: int, player_id: int) -> Dict:
    pool = await _get_pool()
    async with pool.acquire() as c:
        existing = await c.fetchrow(
            "SELECT * FROM registrations WHERE tournament_id=$1 AND player_id=$2",
            tid, player_id
        )
        if existing:
            ex = _row(existing)
            if ex["status"] == "cancelled":
                # Re-registering: keep the same table or reassign
                table_num = ex.get("table_number", 0)
                await c.execute(
                    """UPDATE registrations SET status='registered',
                       registered_at=(NOW()::TEXT)
                       WHERE tournament_id=$1 AND player_id=$2""",
                    tid, player_id
                )
                return {"ok": True, "table_number": table_num}
            return {"ok": False, "reason": "already_registered"}

        t = await c.fetchrow(
            """SELECT t.max_players, t.table_count, COUNT(r.id) AS cnt
               FROM tournaments t
               LEFT JOIN registrations r
                      ON r.tournament_id=t.id AND r.status='registered'
               WHERE t.id=$1 GROUP BY t.id""",
            tid
        )
        if t and t["cnt"] >= t["max_players"]:
            return {"ok": False, "reason": "full"}

        # Auto-assign table by round-robin
        tc = int(t["table_count"]) if t and t["table_count"] else 0
        cnt = int(t["cnt"]) if t else 0
        table_num = (cnt % tc + 1) if tc > 0 else 0

        await c.execute(
            "INSERT INTO registrations (tournament_id, player_id, table_number) VALUES ($1,$2,$3)",
            tid, player_id, table_num
        )
        return {"ok": True, "table_number": table_num}


async def unregister_player(tid: int, player_id: int):
    pool = await _get_pool()
    async with pool.acquire() as c:
        await c.execute(
            "UPDATE registrations SET status='cancelled' WHERE tournament_id=$1 AND player_id=$2",
            tid, player_id
        )


async def is_registered(tid: int, player_id: int) -> bool:
    pool = await _get_pool()
    async with pool.acquire() as c:
        row = await c.fetchrow(
            "SELECT 1 FROM registrations WHERE tournament_id=$1 AND player_id=$2 AND status='registered'",
            tid, player_id
        )
        return bool(row)


async def get_my_registration(tid: int, player_id: int) -> Dict:
    """Return registration info including table_number."""
    pool = await _get_pool()
    async with pool.acquire() as c:
        row = await c.fetchrow(
            """SELECT r.status, r.table_number, t.table_count
               FROM registrations r
               JOIN tournaments t ON t.id=r.tournament_id
               WHERE r.tournament_id=$1 AND r.player_id=$2""",
            tid, player_id
        )
        if row and row["status"] == "registered":
            return {
                "registered": True,
                "table_number": row["table_number"] or 0,
                "table_count":  row["table_count"] or 0,
            }
        return {"registered": False, "table_number": 0, "table_count": 0}


async def get_participants(tid: int) -> List[Dict]:
    pool = await _get_pool()
    async with pool.acquire() as c:
        rows = await c.fetch(
            """SELECT p.id, p.tg_id, p.fio, p.username, p.city, p.rating,
                      p.wins_count, p.knockouts, r.registered_at
               FROM registrations r
               JOIN players p ON p.id=r.player_id
               WHERE r.tournament_id=$1 AND r.status='registered'
               ORDER BY r.registered_at ASC""",
            tid
        )
        return [_row(r) for r in rows]


async def get_my_tournaments(player_id: int) -> List[Dict]:
    pool = await _get_pool()
    async with pool.acquire() as c:
        rows = await c.fetch(
            """SELECT t.id, t.title, t.start_time, t.status, t.city,
                      r.status AS reg_status, r.registered_at,
                      gr.place, gr.knockouts, gr.rating_delta, gr.pro_delta, gr.prize
               FROM registrations r
               JOIN tournaments t ON t.id=r.tournament_id
               LEFT JOIN game_results gr
                      ON gr.tournament_id=t.id AND gr.player_id=r.player_id
               WHERE r.player_id=$1
               ORDER BY t.start_time DESC""",
            player_id
        )
        return [_row(r) for r in rows]


# ─── KNOCKOUTS (interim — during active tournament) ─────────────────────────

async def add_knockouts(entries: list) -> None:
    """Increment knockouts counter for players without finishing the tournament."""
    pool = await _get_pool()
    async with pool.acquire() as c:
        for e in entries:
            ko = int(e.get("knockouts", 0))
            if ko > 0:
                await c.execute(
                    "UPDATE players SET knockouts=knockouts+$1 WHERE id=$2",
                    ko, int(e["player_id"])
                )


# ─── RESULTS ─────────────────────────────────────────────────────────────────

async def record_result(tid: int, player_id: int, place: int,
                        knockouts: int = 0, prize: float = 0.0):
    pool = await _get_pool()
    async with pool.acquire() as c:
        t = await c.fetchrow("SELECT max_players FROM tournaments WHERE id=$1", tid)
        max_p = t["max_players"] if t else 100

        rating_delta = max(0, (max_p - place + 1) * 10) + knockouts * 5
        pro_delta    = knockouts * 25.0

        await c.execute(
            """INSERT INTO game_results
               (tournament_id, player_id, place, knockouts, prize, rating_delta, pro_delta)
               VALUES ($1,$2,$3,$4,$5,$6,$7)
               ON CONFLICT (tournament_id, player_id)
               DO UPDATE SET place=$3, knockouts=$4, prize=$5,
                             rating_delta=$6, pro_delta=$7""",
            tid, player_id, place, knockouts, prize, rating_delta, pro_delta
        )

        p = await c.fetchrow("SELECT best_place FROM players WHERE id=$1", player_id)
        best = p["best_place"] if p and p["best_place"] else place
        new_best = min(best, place) if best else place

        await c.execute(
            """UPDATE players SET
               rating      = rating + $1,
               pro_score   = pro_score + $2,
               knockouts   = knockouts + $3,
               games_count = games_count + 1,
               wins_count  = wins_count + $4,
               best_place  = $5
               WHERE id=$6""",
            rating_delta, pro_delta, knockouts,
            1 if place == 1 else 0, new_best, player_id
        )
        await c.execute(
            "UPDATE registrations SET status='finished' WHERE tournament_id=$1 AND player_id=$2",
            tid, player_id
        )
