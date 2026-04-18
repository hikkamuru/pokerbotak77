"""
Telegram notification helper.
Call set_bot(bot) once at startup, then use send(tg_id, text) anywhere.
"""
import logging

_log = logging.getLogger(__name__)
_bot = None


def set_bot(bot) -> None:
    global _bot
    _bot = bot


async def send(tg_id: int, text: str) -> None:
    """Send a Telegram message to a user. Silently swallows all errors."""
    if not _bot or not tg_id:
        return
    try:
        await _bot.send_message(tg_id, text, parse_mode="HTML")
    except Exception as e:
        _log.warning("[notify] failed tg_id=%s: %s", tg_id, e)
