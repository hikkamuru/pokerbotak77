"""
Notification service.
Runs as a background task alongside the bot.
Sends reminders 24h and 1h before each tournament.
"""
import asyncio
import logging
from datetime import datetime, timedelta

import aiosqlite

from app.database import DB_PATH

logger = logging.getLogger(__name__)

# Track which notifications have already been sent (in-memory, resets on restart)
_sent: set[str] = set()


async def _get_upcoming(window_start: datetime, window_end: datetime):
    """Return tournaments starting within [window_start, window_end]."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute(
            """SELECT t.id, t.title, t.start_time, t.address, t.location,
                      p.tg_id, p.full_name
               FROM tournaments t
               JOIN registrations r ON r.tournament_id = t.id AND r.status = 'registered'
               JOIN players p ON p.id = r.player_id
               WHERE t.status = 'upcoming'
                 AND t.start_time >= ?
                 AND t.start_time <  ?
                 AND p.push_notify = 1""",
            (window_start.isoformat(sep=" ")[:16],
             window_end.isoformat(sep=" ")[:16])
        )
        return await rows.fetchall()


async def _send_reminders(bot, hours_before: int):
    now = datetime.now()
    window_start = now + timedelta(hours=hours_before) - timedelta(minutes=5)
    window_end   = now + timedelta(hours=hours_before) + timedelta(minutes=5)

    rows = await _get_upcoming(window_start, window_end)
    for row in rows:
        key = f"{row['id']}:{row['tg_id']}:{hours_before}h"
        if key in _sent:
            continue
        _sent.add(key)

        if hours_before == 24:
            text = (
                f"🔔 <b>Напоминание о турнире!</b>\n\n"
                f"🎯 <b>{row['title']}</b>\n"
                f"📅 Завтра в {row['start_time'][11:16]}\n"
            )
        else:
            text = (
                f"⏰ <b>Турнир начинается через час!</b>\n\n"
                f"🎯 <b>{row['title']}</b>\n"
                f"📅 Сегодня в {row['start_time'][11:16]}\n"
            )
        if row["address"]:
            text += f"📍 {row['address']}\n"

        text += "\nУдачи! 🃏"

        try:
            await bot.send_message(row["tg_id"], text)
            logger.info(f"Reminder {hours_before}h sent to {row['tg_id']} for tournament {row['id']}")
        except Exception as e:
            logger.warning(f"Failed to notify {row['tg_id']}: {e}")
        await asyncio.sleep(0.05)   # rate-limit friendly


async def notification_loop(bot):
    """Run forever, checking for reminders every 5 minutes."""
    logger.info("Notification loop started")
    while True:
        try:
            await _send_reminders(bot, hours_before=24)
            await _send_reminders(bot, hours_before=1)
        except Exception as e:
            logger.error(f"Notification error: {e}")
        await asyncio.sleep(5 * 60)   # check every 5 minutes
