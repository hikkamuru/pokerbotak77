"""
Broadcast service — sends a message to all registered players.
Called from admin handler via /broadcast command.
"""
import asyncio
import logging
from typing import Optional

import aiosqlite
from app.database import DB_PATH

logger = logging.getLogger(__name__)


async def get_all_player_ids(only_push: bool = True) -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT tg_id FROM players WHERE tg_id > 0"
        if only_push:
            query += " AND push_notify = 1"
        rows = await db.execute(query)
        return [r["tg_id"] for r in await rows.fetchall()]


async def broadcast(bot, text: str, only_push: bool = True) -> dict:
    """
    Send text to all players. Returns stats dict.
    """
    ids = await get_all_player_ids(only_push)
    sent = 0
    failed = 0
    for tg_id in ids:
        try:
            await bot.send_message(tg_id, text)
            sent += 1
        except Exception as e:
            logger.warning(f"Broadcast failed for {tg_id}: {e}")
            failed += 1
        await asyncio.sleep(0.05)   # ~20 msg/sec, Telegram limit is 30
    return {"sent": sent, "failed": failed, "total": len(ids)}
