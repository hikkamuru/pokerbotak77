import aiosqlite
import asyncio
from datetime import datetime
from config import config

DB_PATH = config.DB_PATH


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                full_name TEXT,
                nickname TEXT,
                city TEXT DEFAULT 'Москва',
                rating INTEGER DEFAULT 1000,
                pro_rating REAL DEFAULT 0.0,
                knockouts INTEGER DEFAULT 0,
                games_played INTEGER DEFAULT 0,
                games_won INTEGER DEFAULT 0,
                free_entries INTEGER DEFAULT 0,
                push_notifications INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS tournaments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                rules TEXT,
                address TEXT,
                city TEXT DEFAULT 'Москва',
                max_players INTEGER DEFAULT 100,
                current_players INTEGER DEFAULT 0,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                status TEXT DEFAULT 'upcoming',
                buy_in INTEGER DEFAULT 0,
                prize_pool TEXT,
                banner_url TEXT,
                logo_url TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS tournament_registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                place INTEGER,
                knockouts INTEGER DEFAULT 0,
                prize REAL DEFAULT 0,
                registered_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (tournament_id) REFERENCES tournaments(id),
                FOREIGN KEY (player_id) REFERENCES players(id),
                UNIQUE(tournament_id, player_id)
            );

            CREATE TABLE IF NOT EXISTS game_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                place INTEGER,
                knockouts INTEGER DEFAULT 0,
                rating_change INTEGER DEFAULT 0,
                pro_change REAL DEFAULT 0,
                recorded_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (tournament_id) REFERENCES tournaments(id),
                FOREIGN KEY (player_id) REFERENCES players(id)
            );

            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER NOT NULL,
                table_number INTEGER,
                date TEXT NOT NULL,
                time_slot TEXT NOT NULL,
                duration INTEGER DEFAULT 2,
                players_count INTEGER DEFAULT 2,
                status TEXT DEFAULT 'pending',
                comment TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (player_id) REFERENCES players(id)
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER NOT NULL,
                tournament_id INTEGER,
                type TEXT NOT NULL,
                message TEXT,
                is_read INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (player_id) REFERENCES players(id)
            );

            CREATE INDEX IF NOT EXISTS idx_players_telegram_id ON players(telegram_id);
            CREATE INDEX IF NOT EXISTS idx_tournaments_status ON tournaments(status);
            CREATE INDEX IF NOT EXISTS idx_registrations_tournament ON tournament_registrations(tournament_id);
            CREATE INDEX IF NOT EXISTS idx_registrations_player ON tournament_registrations(player_id);
            CREATE INDEX IF NOT EXISTS idx_results_player ON game_results(player_id);
        """)
        await db.commit()
    print("✅ База данных инициализирована")


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


if __name__ == "__main__":
    asyncio.run(init_db())
