import json
import hmac
import hashlib
from pathlib import Path
from urllib.parse import unquote, parse_qsl

from aiohttp import web
from aiohttp.web_middlewares import middleware

from app.database import (
    get_tournaments, get_tournament, get_player_by_tg,
    get_or_create_player, complete_player_profile, update_player_profile,
    register_player, unregister_player, is_registered,
    get_tournament_participants, get_leaderboard, get_player_tournaments,
    create_tournament, update_tournament, update_tournament_status, delete_tournament,
    record_result, get_all_players, admin_update_player, get_admin_stats,
    get_all_bookings, update_booking_status,
)
from config.settings import settings

TEMPLATE_DIR = Path(__file__).parent / "templates"
routes = web.RouteTableDef()

# Build allowed origins from settings
_EXTRA_ORIGINS = {
    "http://localhost:8080",
    "http://127.0.0.1:8080",
}
if settings.WEBAPP_URL:
    _EXTRA_ORIGINS.add(settings.WEBAPP_URL.rstrip("/"))
if getattr(settings, "SITE_URL", None):
    _EXTRA_ORIGINS.add(settings.SITE_URL.rstrip("/"))

ALLOWED_ORIGINS = _EXTRA_ORIGINS


@middleware
async def cors_middleware(request: web.Request, handler):
    origin = request.headers.get("Origin", "")
    if request.method == "OPTIONS":
        return web.Response(
            status=204,
            headers={
                "Access-Control-Allow-Origin": origin or "*",
                "Access-Control-Allow-Headers": "Content-Type, X-Telegram-Init-Data",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Max-Age": "86400",
            }
        )
    response = await handler(request)
    if origin in ALLOWED_ORIGINS or not origin:
        allow_origin = origin or "*"
    else:
        allow_origin = "*"
    response.headers["Access-Control-Allow-Origin"] = allow_origin
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Telegram-Init-Data"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response


# ── AUTH ─────────────────────────────────────────────────────────────────────

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


def is_admin(tg_id: int) -> bool:
    return tg_id in settings.admin_list


def json_response(data, status=200):
    return web.Response(
        text=json.dumps(data, ensure_ascii=False, default=str),
        content_type="application/json",
        status=status
    )


# ── PAGES ─────────────────────────────────────────────────────────────────────

@routes.options("/{path_info:.*}")
async def options_handler(request):
    origin = request.headers.get("Origin", "")
    return web.Response(
        status=204,
        headers={
            "Access-Control-Allow-Origin": origin or "*",
            "Access-Control-Allow-Headers": "Content-Type, X-Telegram-Init-Data",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        }
    )


@routes.get("/")
async def index(request):
    html = (TEMPLATE_DIR / "index.html").read_text(encoding="utf-8")
    api_base = settings.API_URL.rstrip("/") if settings.API_URL else ""
    html = html.replace("__API_BASE_URL__", api_base)
    return web.Response(text=html, content_type="text/html")


# ── PUBLIC API ────────────────────────────────────────────────────────────────

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


@routes.get("/api/leaderboard")
async def api_leaderboard(request):
    data = await get_leaderboard(limit=50)
    return json_response(data)


# ── PROFILE API ───────────────────────────────────────────────────────────────

@routes.get("/api/my-profile")
async def api_my_profile(request):
    user = get_tg_user(request)
    if not user:
        return json_response({"error": "unauthorized"}, 401)
    player = await get_player_by_tg(user["id"])
    if not player:
        # Auto-create from Telegram data
        player = await get_or_create_player(
            tg_id=user["id"],
            username=user.get("username", ""),
            full_name=user.get("first_name", "") + (" " + user.get("last_name", "") if user.get("last_name") else ""),
        )
    result = dict(player)
    result["is_admin"] = is_admin(user["id"])
    result["tg_first_name"] = user.get("first_name", "")
    result["tg_last_name"] = user.get("last_name", "")
    result["tg_username"] = user.get("username", "")
    result["tg_photo_url"] = user.get("photo_url", "")
    return json_response(result)


@routes.post("/api/profile/complete")
async def api_profile_complete(request):
    """Save extended profile data (nickname, email, birthday, referral)."""
    user = get_tg_user(request)
    if not user:
        return json_response({"error": "unauthorized"}, 401)

    try:
        body = await request.json()
    except Exception:
        return json_response({"error": "invalid json"}, 400)

    game_nickname = (body.get("game_nickname") or "").strip()
    if not game_nickname:
        return json_response({"error": "game_nickname required"}, 400)

    # Ensure player exists first
    player = await get_player_by_tg(user["id"])
    if not player:
        player = await get_or_create_player(
            tg_id=user["id"],
            username=user.get("username", ""),
            full_name=user.get("first_name", "") + (" " + user.get("last_name", "") if user.get("last_name") else ""),
        )

    updated = await complete_player_profile(
        tg_id=user["id"],
        game_nickname=game_nickname,
        email=body.get("email") or None,
        birth_date=body.get("birth_date") or None,
        referral_code=body.get("referral_code") or None,
        photo_url=body.get("photo_url") or None,
    )
    updated["is_admin"] = is_admin(user["id"])
    return json_response(updated)


@routes.post("/api/profile/update")
async def api_profile_update(request):
    user = get_tg_user(request)
    if not user:
        return json_response({"error": "unauthorized"}, 401)
    try:
        body = await request.json()
    except Exception:
        return json_response({"error": "invalid json"}, 400)
    updated = await update_player_profile(user["id"], body)
    updated["is_admin"] = is_admin(user["id"])
    return json_response(updated)


@routes.get("/api/my-tournaments")
async def api_my_tournaments(request):
    user = get_tg_user(request)
    if not user:
        return json_response({"error": "unauthorized"}, 401)
    player = await get_player_by_tg(user["id"])
    if not player:
        return json_response([])
    data = await get_player_tournaments(player["id"])
    return json_response(data)


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
    if not player.get("profile_complete"):
        return json_response({"ok": False, "reason": "profile_incomplete"}, 403)
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


# ── ADMIN API ─────────────────────────────────────────────────────────────────

def require_admin(request: web.Request):
    """Returns (user, None) or (None, error_response)."""
    user = get_tg_user(request)
    if not user:
        return None, json_response({"error": "unauthorized"}, 401)
    if not is_admin(user["id"]):
        return None, json_response({"error": "forbidden"}, 403)
    return user, None


@routes.get("/api/admin/stats")
async def api_admin_stats(request):
    user, err = require_admin(request)
    if err:
        return err
    data = await get_admin_stats()
    return json_response(data)


@routes.get("/api/admin/players")
async def api_admin_players(request):
    user, err = require_admin(request)
    if err:
        return err
    search = request.rel_url.query.get("q", "")
    data = await get_all_players(search=search)
    return json_response(data)


@routes.put("/api/admin/player/{id}")
async def api_admin_update_player(request):
    user, err = require_admin(request)
    if err:
        return err
    try:
        body = await request.json()
    except Exception:
        return json_response({"error": "invalid json"}, 400)
    updated = await admin_update_player(int(request.match_info["id"]), body)
    return json_response(updated)


@routes.get("/api/admin/tournaments")
async def api_admin_tournaments(request):
    user, err = require_admin(request)
    if err:
        return err
    status = request.rel_url.query.get("status", "upcoming")
    data = await get_tournaments(status)
    return json_response(data)


@routes.post("/api/admin/tournament")
async def api_admin_create_tournament(request):
    user, err = require_admin(request)
    if err:
        return err
    try:
        body = await request.json()
    except Exception:
        return json_response({"error": "invalid json"}, 400)
    if not body.get("title") or not body.get("start_time"):
        return json_response({"error": "title and start_time required"}, 400)
    tour_id = await create_tournament(body)
    return json_response({"ok": True, "id": tour_id})


@routes.put("/api/admin/tournament/{id}")
async def api_admin_update_tournament(request):
    user, err = require_admin(request)
    if err:
        return err
    try:
        body = await request.json()
    except Exception:
        return json_response({"error": "invalid json"}, 400)
    await update_tournament(int(request.match_info["id"]), body)
    return json_response({"ok": True})


@routes.delete("/api/admin/tournament/{id}")
async def api_admin_delete_tournament(request):
    user, err = require_admin(request)
    if err:
        return err
    await delete_tournament(int(request.match_info["id"]))
    return json_response({"ok": True})


@routes.post("/api/admin/tournament/{id}/finish")
async def api_admin_finish_tournament(request):
    """Record results and mark tournament as finished.
    Body: { "results": [ { "player_id": int, "place": int, "knockouts": int, "prize": float } ] }
    """
    user, err = require_admin(request)
    if err:
        return err
    try:
        body = await request.json()
    except Exception:
        return json_response({"error": "invalid json"}, 400)

    tour_id = int(request.match_info["id"])
    results = body.get("results", [])
    for r in results:
        await record_result(
            tournament_id=tour_id,
            player_id=int(r["player_id"]),
            place=int(r["place"]),
            knockouts=int(r.get("knockouts", 0)),
            prize=float(r.get("prize", 0.0)),
        )
    await update_tournament_status(tour_id, "finished")
    return json_response({"ok": True})


@routes.get("/api/admin/bookings")
async def api_admin_bookings(request):
    user, err = require_admin(request)
    if err:
        return err
    status = request.rel_url.query.get("status", "pending")
    data = await get_all_bookings(status)
    return json_response(data)


@routes.post("/api/admin/booking/{id}/status")
async def api_admin_booking_status(request):
    user, err = require_admin(request)
    if err:
        return err
    try:
        body = await request.json()
    except Exception:
        return json_response({"error": "invalid json"}, 400)
    status = body.get("status", "confirmed")
    await update_booking_status(int(request.match_info["id"]), status)
    return json_response({"ok": True})


# ── SERVER ────────────────────────────────────────────────────────────────────

def create_app() -> web.Application:
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_routes(routes)
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.router.add_static("/static", static_dir)
    return app


async def run_webapp():
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.WEBAPP_HOST, settings.WEBAPP_PORT)
    await site.start()
    print(f"Mini App running on port {settings.WEBAPP_PORT}")
    return runner
