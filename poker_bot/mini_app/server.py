import json
import hmac
import hashlib
from pathlib import Path
from urllib.parse import unquote, parse_qsl

from aiohttp import web
from aiohttp.web_middlewares import middleware

from app.database import (
    get_tournaments, get_tournament, get_player_by_tg,
    register_player, unregister_player, is_registered,
    get_tournament_participants, get_leaderboard
)
from config.settings import settings

TEMPLATE_DIR = Path(__file__).parent / "templates"
routes = web.RouteTableDef()

ALLOWED_ORIGINS = {
    settings.WEBAPP_URL.rstrip("/"),
    "http://localhost:8080",
    "http://127.0.0.1:8080",
}


@middleware
async def cors_middleware(request: web.Request, handler):
    origin = request.headers.get("Origin", "")
    response = await handler(request)
    if origin in ALLOWED_ORIGINS or not ALLOWED_ORIGINS - {"http://localhost:8080", "http://127.0.0.1:8080"}:
        response.headers["Access-Control-Allow-Origin"] = origin or "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Telegram-Init-Data"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


def validate_init_data(init_data: str) -> dict | None:
    """Validate Telegram WebApp initData signature."""
    try:
        params = dict(parse_qsl(init_data, strict_parsing=True))
        hash_val = params.pop("hash", None)
        if not hash_val:
            return None
        data_check = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
        secret = hmac.new(b"WebAppData", settings.BOT_TOKEN.encode(), hashlib.sha256).digest()
        expected = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, hash_val):
            return None
        user_data = json.loads(params.get("user", "{}"))
        return user_data
    except Exception:
        return None


def get_tg_user(request: web.Request) -> dict | None:
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    if not init_data:
        return None
    return validate_init_data(init_data)


def json_response(data, status=200):
    return web.Response(
        text=json.dumps(data, ensure_ascii=False),
        content_type="application/json",
        status=status
    )


# ── PAGES ────────────────────────────────────────────────────────────────────

@routes.options("/{path_info:.*}")
async def options_handler(request):
    """Handle CORS preflight requests."""
    origin = request.headers.get("Origin", "")
    return web.Response(
        status=204,
        headers={
            "Access-Control-Allow-Origin": origin or "*",
            "Access-Control-Allow-Headers": "Content-Type, X-Telegram-Init-Data",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        }
    )


@routes.get("/")
async def index(request):
    html = (TEMPLATE_DIR / "index.html").read_text(encoding="utf-8")
    # Inject the API base URL so the static frontend knows where to call
    api_base = settings.API_URL.rstrip("/") if settings.API_URL else ""
    html = html.replace("__API_BASE_URL__", api_base)
    return web.Response(text=html, content_type="text/html")


# ── API ──────────────────────────────────────────────────────────────────────

@routes.get("/api/tournaments")
async def api_tournaments(request):
    status = request.rel_url.query.get("status", "upcoming")
    data = await get_tournaments(status)
    return json_response(data)


@routes.get("/api/tournament/{id}")
async def api_tournament(request):
    t = await get_tournament(int(request.match_info["id"]))
    if not t:
        return json_response({"error": "not found"}, 404)
    return json_response(t)


@routes.get("/api/tournament/{id}/participants")
async def api_participants(request):
    data = await get_tournament_participants(int(request.match_info["id"]))
    return json_response(data)


@routes.get("/api/my-profile")
async def api_my_profile(request):
    user = get_tg_user(request)
    if not user:
        return json_response({"error": "unauthorized"}, 401)
    player = await get_player_by_tg(user["id"])
    if not player:
        return json_response({"error": "player not found"}, 404)
    return json_response(player)


@routes.get("/api/my-registration/{id}")
async def api_my_registration(request):
    user = get_tg_user(request)
    if not user:
        return json_response({"registered": False})
    player = await get_player_by_tg(user["id"])
    if not player:
        return json_response({"registered": False})
    registered = await is_registered(int(request.match_info["id"]), player["id"])
    return json_response({"registered": registered})


@routes.post("/api/register/{id}")
async def api_register(request):
    user = get_tg_user(request)
    if not user:
        return json_response({"ok": False, "reason": "unauthorized"}, 401)
    player = await get_player_by_tg(user["id"])
    if not player:
        return json_response({"ok": False, "reason": "player not found"}, 404)
    result = await register_player(int(request.match_info["id"]), player["id"])
    return json_response(result)


@routes.post("/api/unregister/{id}")
async def api_unregister(request):
    user = get_tg_user(request)
    if not user:
        return json_response({"ok": False, "reason": "unauthorized"}, 401)
    player = await get_player_by_tg(user["id"])
    if not player:
        return json_response({"ok": False, "reason": "player not found"}, 404)
    await unregister_player(int(request.match_info["id"]), player["id"])
    return json_response({"ok": True})


@routes.get("/api/leaderboard")
async def api_leaderboard(request):
    data = await get_leaderboard(limit=50)
    return json_response(data)


# ── SERVER ───────────────────────────────────────────────────────────────────

def create_app() -> web.Application:
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_routes(routes)
    # Serve static files if any
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.router.add_static("/static", static_dir)
    return app


async def run_webapp():
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", settings.WEBAPP_PORT)
    await site.start()
    print(f"Mini App running on port {settings.WEBAPP_PORT}")
    return runner
