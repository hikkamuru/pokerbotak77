"""
python seed.py

Populates the database with demo data so you can test the Mini App right away.
Run ONCE after first launch.
"""
import asyncio
from datetime import datetime, timedelta
from app.database import init_db, create_tournament, get_or_create_player
import aiosqlite
from app.database import DB_PATH


DEMO_PLAYERS = [
    (100000001, "JojiAndre",    "Андрей Жожи"),
    (100000002, "DecumaN",      "Никита Декума"),
    (100000003, "pension_pro",  "Пенсионер Про"),
    (100000004, "megaultra",    "Мегаультра Про"),
    (100000005, "enjoy_poker",  "Иван Энджой"),
    (100000006, "bluff_king",   "Сергей Блефф"),
    (100000007, "all_in_alex",  "Александр Олл-Ин"),
    (100000008, "river_rat",    "Денис Ривер"),
]

DEMO_TOURNAMENTS = [
    {
        "title": "DEEP LIMITED",
        "description": "Классический турнир с глубоким стеком. Уровни по 20 минут.",
        "rules": "Ре-бай запрещён. Опоздание более 30 минут = блайнды списываются.",
        "location": "Покер-клуб",
        "address": "м. Курская, Нижний Сусальный переулок, 5с1",
        "city": "Москва",
        "start_time": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d 19:00"),
        "max_players": 100,
        "buy_in": 0,
        "prize_pool": "Кубок + звание",
    },
    {
        "title": "PHOENIX TOURNAMENT",
        "description": "Турнир для опытных игроков. Быстрая структура.",
        "rules": "Один ре-бай в первые 3 уровня.",
        "location": "Покер-клуб",
        "address": "м. Курская, Нижний Сусальный переулок, 5с1",
        "city": "Москва",
        "start_time": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d 19:00"),
        "max_players": 100,
        "buy_in": 0,
        "prize_pool": "Кубок Феникса",
    },
    {
        "title": "PHOENIX · BLACK EDITION",
        "description": "Закрытый турнир. Только для игроков с рейтингом 5000+.",
        "rules": "Вход только по приглашению. Ре-баи запрещены.",
        "location": "Покер-клуб VIP",
        "address": "м. Курская, Нижний Сусальный переулок, 5с1",
        "city": "Москва",
        "start_time": (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d 19:00"),
        "max_players": 50,
        "buy_in": 0,
        "prize_pool": "Чёрный кубок",
    },
    {
        "title": "BOUNTY TOURNAMENT",
        "description": "Баунти-турнир: получи приз за каждого выбитого игрока!",
        "rules": "За каждый нок — бонусные очки в рейтинг × 2.",
        "location": "Покер-клуб",
        "address": "м. Курская, Нижний Сусальный переулок, 5с1",
        "city": "Москва",
        "start_time": (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d 19:00"),
        "max_players": 80,
        "buy_in": 0,
        "prize_pool": "Баунти-пул",
    },
]


async def seed():
    await init_db()
    print("✅ Database initialized")

    # Create players
    players = []
    for tg_id, username, full_name in DEMO_PLAYERS:
        p = await get_or_create_player(tg_id, username, full_name)
        players.append(p)
    print(f"✅ {len(players)} demo players created")

    # Give them some rating/knockouts
    demo_stats = [
        (575.07, 11, 8885, 3),
        (432.62, 9,  7639, 2),
        (0,      4,  7463, 1),
        (0,      11, 7312, 4),
        (0,      0,  6601, 0),
        (120.5,  6,  5200, 2),
        (88.0,   3,  4100, 1),
        (55.0,   2,  3800, 0),
    ]
    async with aiosqlite.connect(DB_PATH) as db:
        for i, p in enumerate(players):
            pro, knockouts, rating, wins = demo_stats[i]
            await db.execute(
                """UPDATE players SET pro_score=?, knockouts=?, rating=?,
                   wins_count=?, games_count=? WHERE id=?""",
                (pro, knockouts, rating, wins, wins + knockouts, p["id"])
            )
        await db.commit()
    print("✅ Demo stats applied")

    # Create tournaments
    tour_ids = []
    for t in DEMO_TOURNAMENTS:
        tid = await create_tournament(t)
        tour_ids.append(tid)
    print(f"✅ {len(tour_ids)} tournaments created")

    # Register some players to first tournament
    async with aiosqlite.connect(DB_PATH) as db:
        for p in players[:5]:
            try:
                await db.execute(
                    "INSERT OR IGNORE INTO registrations (tournament_id, player_id) VALUES (?,?)",
                    (tour_ids[0], p["id"])
                )
            except Exception:
                pass
        # Fill the first tournament count to 82 with fake registrations
        for fake_id in range(200001, 200079):
            try:
                await db.execute(
                    "INSERT OR IGNORE INTO players (tg_id, full_name) VALUES (?,?)",
                    (fake_id, f"Игрок {fake_id - 200000}")
                )
                row = await db.execute("SELECT id FROM players WHERE tg_id=?", (fake_id,))
                pid = (await row.fetchone())["id"]
                await db.execute(
                    "INSERT OR IGNORE INTO registrations (tournament_id, player_id) VALUES (?,?)",
                    (tour_ids[0], pid)
                )
            except Exception:
                pass
        await db.commit()
    print(f"✅ Registrations seeded (tournament 1 has ~82 players)")

    print("\n🎉 Seed complete! You can now run: python main.py")


if __name__ == "__main__":
    asyncio.run(seed())
