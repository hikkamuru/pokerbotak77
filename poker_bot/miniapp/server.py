from aiohttp import web
import json
from pathlib import Path

from services.player_service import get_or_create_player, get_player_by_telegram_id, get_leaderboard, update_push_notifications
from services.tournament_service import get_upcoming_tournaments, get_past_tournaments, get_nearest_tournament, get_tournament_by_id, register_player
from config import config

import hmac
import hashlib
import urllib.parse
import time

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"


def verify_telegram_data(init_data: str, bot_token: str) -> dict | None:
    """Verify Telegram WebApp init data and return user data if valid"""
    if not init_data:
        return None
    try:
        parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
        received_hash = parsed.pop("hash", "")
        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(parsed.items())
        )
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_hash, received_hash):
            return None
        # Check auth_date not too old (1 hour)
        auth_date = int(parsed.get("auth_date", 0))
        if time.time() - auth_date > 3600:
            return None
        user_data = json.loads(parsed.get("user", "{}"))
        return user_data
    except Exception:
        return None


async def get_current_user(request: web.Request) -> dict | None:
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    user_data = verify_telegram_data(init_data, config.BOT_TOKEN)
    if not user_data:
        # Dev mode: allow if no init data (testing)
        if config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
            return {"id": 0, "username": "dev", "first_name": "Dev"}
        return None
    # Auto-create player
    player = await get_or_create_player(
        telegram_id=user_data["id"],
        username=user_data.get("username", ""),
        full_name=f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
    )
    return player


# ── Routes ───────────────────────────────────────────────────────────────────
async def index(request: web.Request):
    html = (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")
    html = html.replace("{{ club_name }}", config.CLUB_NAME)
    html = html.replace("{{ club_address }}", config.CLUB_ADDRESS)
    html = html.replace("'{{ club_name }}'", f"'{config.CLUB_NAME}'")
    return web.Response(text=html, content_type="text/html", charset="utf-8")


async def api_me(request: web.Request):
    player = await get_current_user(request)
    if not player:
        return web.json_response({"error": "unauthorized"}, status=401)
    return web.json_response(player)


async def api_tournaments(request: web.Request):
    status = request.rel_url.query.get("status", "upcoming")
    if status == "upcoming":
        tournaments = await get_upcoming_tournaments()
    else:
        tournaments = await get_past_tournaments()
    return web.json_response(tournaments)


async def api_nearest_tournament(request: web.Request):
    t = await get_nearest_tournament()
    if not t:
        return web.json_response(None)
    return web.json_response(t)


async def api_tournament(request: web.Request):
    tournament_id = int(request.match_info["id"])
    t = await get_tournament_by_id(tournament_id)
    if not t:
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response(t)


async def api_register_tournament(request: web.Request):
    player = await get_current_user(request)
    if not player:
        return web.json_response({"error": "unauthorized"}, status=401)
    tournament_id = int(request.match_info["id"])
    result = await register_player(tournament_id, player["id"])
    messages = {
        "success": "Вы успешно зарегистрированы!",
        "already_registered": "Вы уже зарегистрированы",
        "full": "Все места заняты",
        "not_found": "Турнир не найден"
    }
    return web.json_response({
        "status": result,
        "message": messages.get(result, "Ошибка")
    })


async def api_leaderboard(request: web.Request):
    players = await get_leaderboard(limit=50)
    return web.json_response(players)


async def api_toggle_notifications(request: web.Request):
    player = await get_current_user(request)
    if not player:
        return web.json_response({"error": "unauthorized"}, status=401)
    current = player.get("push_notifications", 1)
    await update_push_notifications(player["telegram_id"], not bool(current))
    return web.json_response({"ok": True})


def create_app() -> web.Application:
    app = web.Application()
    # Static files
    app.router.add_static("/static", STATIC_DIR)
    # Pages
    app.router.add_get("/", index)
    # API
    app.router.add_get("/api/me", api_me)
    app.router.add_get("/api/tournaments", api_tournaments)
    app.router.add_get("/api/nearest-tournament", api_nearest_tournament)
    app.router.add_get("/api/tournament/{id}", api_tournament)
    app.router.add_get("/api/register-tournament/{id}", api_register_tournament)
    app.router.add_get("/api/leaderboard", api_leaderboard)
    app.router.add_get("/api/toggle-notifications", api_toggle_notifications)
    return app


if __name__ == "__main__":
    app = create_app()
    web.run_app(app, host=config.WEBAPP_HOST, port=config.WEBAPP_PORT)
