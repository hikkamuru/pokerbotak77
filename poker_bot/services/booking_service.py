from database.models import get_db
from typing import Optional


AVAILABLE_SLOTS = ["16:00", "17:00", "18:00", "19:00", "20:00", "21:00", "22:00"]
TABLES_COUNT = 8


async def get_available_slots(date: str) -> list:
    async with await get_db() as db:
        cursor = await db.execute(
            """SELECT time_slot, table_number FROM bookings
               WHERE date=? AND status IN ('pending', 'confirmed')""",
            (date,)
        )
        booked = await cursor.fetchall()
        booked_slots = {}
        for b in booked:
            slot = b["time_slot"]
            if slot not in booked_slots:
                booked_slots[slot] = 0
            booked_slots[slot] += 1
        result = []
        for slot in AVAILABLE_SLOTS:
            taken = booked_slots.get(slot, 0)
            result.append({
                "time": slot,
                "available": taken < TABLES_COUNT,
                "tables_left": TABLES_COUNT - taken
            })
        return result


async def create_booking(player_id: int, date: str, time_slot: str,
                         players_count: int = 2, comment: str = "") -> Optional[int]:
    async with await get_db() as db:
        # Find free table
        cursor = await db.execute(
            """SELECT table_number FROM bookings
               WHERE date=? AND time_slot=? AND status IN ('pending','confirmed')""",
            (date, time_slot)
        )
        taken = {r["table_number"] for r in await cursor.fetchall()}
        free_table = None
        for i in range(1, TABLES_COUNT + 1):
            if i not in taken:
                free_table = i
                break
        if free_table is None:
            return None
        cursor = await db.execute(
            """INSERT INTO bookings (player_id, table_number, date, time_slot, players_count, comment)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (player_id, free_table, date, time_slot, players_count, comment)
        )
        await db.commit()
        return cursor.lastrowid


async def get_player_bookings(player_id: int) -> list:
    async with await get_db() as db:
        cursor = await db.execute(
            """SELECT * FROM bookings WHERE player_id=?
               ORDER BY date DESC, time_slot DESC""",
            (player_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def cancel_booking(booking_id: int, player_id: int) -> bool:
    async with await get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM bookings WHERE id=? AND player_id=? AND status='pending'",
            (booking_id, player_id)
        )
        if not await cursor.fetchone():
            return False
        await db.execute(
            "UPDATE bookings SET status='cancelled' WHERE id=?",
            (booking_id,)
        )
        await db.commit()
        return True


async def get_all_bookings(date: str = None) -> list:
    async with await get_db() as db:
        if date:
            cursor = await db.execute(
                """SELECT b.*, p.telegram_id, p.nickname, p.full_name
                   FROM bookings b JOIN players p ON b.player_id=p.id
                   WHERE b.date=?
                   ORDER BY b.time_slot""",
                (date,)
            )
        else:
            cursor = await db.execute(
                """SELECT b.*, p.telegram_id, p.nickname, p.full_name
                   FROM bookings b JOIN players p ON b.player_id=p.id
                   WHERE b.status IN ('pending','confirmed')
                   ORDER BY b.date, b.time_slot"""
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def confirm_booking(booking_id: int) -> bool:
    async with await get_db() as db:
        await db.execute(
            "UPDATE bookings SET status='confirmed' WHERE id=?",
            (booking_id,)
        )
        await db.commit()
        return True
