import json
import hmac
import hashlib
from pathlib import Path
from urllib.parse import parse_qsl

from aiohttp import web
from aiohttp.web_middlewares import middleware

from app.database import (
    get_or_create_player, complete_profile, get_player_by_tg,
    get_player_by_id, get_all_players, admin_update_player, get_admin_stats,
    get_leaderboard, get_tournaments, get_tournament, create_tournament,
    update_tournament_status, delete_tournament,
    register_player, unregister_player, is_registered,
    get_participants, get_my_tournaments, record_result,
)
from config.settings import settings

TEMPLATE_DIR = Path(__file__).parent / "templates"
routes = web.RouteTableDef()


# ── CORS ─────────────────────────────────────────────────────────────────────

CORS_HEADERS = {
    "Access-Control-Allow-Headers": "Content-Type, X-Telegram-Init-Data",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Max-Age": "86400",
}


@middleware
async def cors_middleware(request: web.Request, handler):
    origin = request.headers.get("Origin", "*")
    if request.method == "OPTIONS":
        return web.Response(status=204, headers={
            "Access-Control-Allow-Origin": origin, **CORS_HEADERS
        })
    resp = await handler(request)
    resp.headers["Access-Control-Allow-Origin"] = origin
    for k, v in CORS_HEADERS.items():
        resp.headers[k] = v
    return resp


@routes.options("/{p:.*}")
async def preflight(request):
    origin = request.headers.get("Origin", "*")
    return web.Response(status=204, headers={
        "Access-Control-Allow-Origin": origin, **CORS_HEADERS
    })


# ── AUTH ─────────────────────────────────────────────────────────────────────

def validate_init_data(raw: str) -> dict | None:
    import logging
    try:
        params = dict(parse_qsl(raw, strict_parsing=False))
        h = params.pop("hash", None)
        if not h:
            logging.warning("[AUTH] no hash in initData")
            return None
        check_str = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
        secret = hmac.new(b"WebAppData", settings.BOT_TOKEN.strip().encode(), hashlib.sha256).digest()
        expected = hmac.new(secret, check_str.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, h):
            logging.warning(f"[AUTH] hash mismatch. expected={expected[:10]}... got={h[:10]}...")
            return None
        return json.loads(params.get("user", "{}"))
    except Exception as e:
        logging.warning(f"[AUTH] exception: {e}")
        return None


def get_tg_user(request: web.Request) -> dict | None:
    raw = request.headers.get("X-Telegram-Init-Data", "")
    if not raw:
        import logging
        logging.warning("[AUTH] X-Telegram-Init-Data header is empty")
        return None
    return validate_init_data(raw)


def is_admin(tg_id: int) -> bool:
    return tg_id in settings.admin_list


def ok(data=None, status=200):
    return web.Response(
        text=json.dumps({} if data is None else data, ensure_ascii=False, default=str),
        content_type="application/json",
        status=status,
    )


def err(msg: str, status=400):
    return ok({"error": msg}, status)


def require_auth(request):
    """Returns (user_dict, None) or (None, error_response)."""
    u = get_tg_user(request)
    if not u:
        return None, err("unauthorized", 401)
    return u, None


def require_admin(request):
    u, e = require_auth(request)
    if e:
        return None, e
    if not is_admin(u["id"]):
        return None, err("forbidden", 403)
    return u, None


# ── PAGE ─────────────────────────────────────────────────────────────────────

@routes.get("/")
async def index(request):
    html = (TEMPLATE_DIR / "index.html").read_text(encoding="utf-8")
    api = (settings.API_URL or "").rstrip("/")
    html = html.replace("__API_BASE_URL__", api)
    return web.Response(text=html, content_type="text/html")


# ── PROFILE ──────────────────────────────────────────────────────────────────

@routes.get("/api/me")
async def api_me(request):
    u, e = require_auth(request)
    if e:
        return e
    tg_name = (u.get("first_name", "") + " " + u.get("last_name", "")).strip()
    player = await get_or_create_player(
        tg_id=u["id"],
        username=u.get("username", ""),
        tg_name=tg_name,
    )
    player["is_admin"] = is_admin(u["id"])
    player["tg_first_name"] = u.get("first_name", "")
    player["tg_username"]   = u.get("username", "")
    return ok(player)


@routes.post("/api/register-profile")
async def api_register_profile(request):
    """First-time registration: FIO, phone, city."""
    u, e = require_auth(request)
    if e:
        return e
    try:
        body = await request.json()
    except Exception:
        return err("invalid json")

    fio   = (body.get("fio") or "").strip()
    phone = (body.get("phone") or "").strip()
    city  = (body.get("city") or "").strip()

    if len(fio.split()) < 2:
        return err("Введите ФИО (минимум имя и фамилия)")
    if not phone or len(phone) < 10:
        return err("Введите корректный номер телефона")
    if city not in ("Брянск", "Москва"):
        return err("Выберите город")

    # Ensure row exists
    tg_name = (u.get("first_name", "") + " " + u.get("last_name", "")).strip()
    await get_or_create_player(u["id"], u.get("username", ""), tg_name)
    player = await complete_profile(u["id"], fio, phone, city)
    player["is_admin"] = is_admin(u["id"])
    return ok(player)


@routes.get("/api/my-games")
async def api_my_games(request):
    u, e = require_auth(request)
    if e:
        return e
    p = await get_player_by_tg(u["id"])
    if not p:
        return ok([])
    return ok(await get_my_tournaments(p["id"]))


# ── TOURNAMENTS ──────────────────────────────────────────────────────────────

@routes.get("/api/tournaments")
async def api_tournaments(request):
    status = request.rel_url.query.get("status", "upcoming")
    city   = request.rel_url.query.get("city", "")
    return ok(await get_tournaments(status, city))


@routes.get("/api/tournament/{id}")
async def api_tournament(request):
    t = await get_tournament(int(request.match_info["id"]))
    return ok(t) if t else err("not found", 404)


@routes.get("/api/tournament/{id}/participants")
async def api_participants(request):
    return ok(await get_participants(int(request.match_info["id"])))


@routes.get("/api/my-reg/{id}")
async def api_my_reg(request):
    u, e = require_auth(request)
    if e:
        return ok({"registered": False})
    p = await get_player_by_tg(u["id"])
    if not p:
        return ok({"registered": False})
    reg = await is_registered(int(request.match_info["id"]), p["id"])
    return ok({"registered": reg})


@routes.post("/api/join/{id}")
async def api_join(request):
    u, e = require_auth(request)
    if e:
        return e
    p = await get_player_by_tg(u["id"])
    if not p:
        return err("player not found", 404)
    if not p.get("profile_complete"):
        return err("profile_incomplete", 403)
    return ok(await register_player(int(request.match_info["id"]), p["id"]))


@routes.post("/api/leave/{id}")
async def api_leave(request):
    u, e = require_auth(request)
    if e:
        return e
    p = await get_player_by_tg(u["id"])
    if not p:
        return err("player not found", 404)
    await unregister_player(int(request.match_info["id"]), p["id"])
    return ok({"ok": True})


# ── LEADERBOARD ──────────────────────────────────────────────────────────────

@routes.get("/api/leaderboard")
async def api_leaderboard(request):
    city = request.rel_url.query.get("city", "")
    return ok(await get_leaderboard(city))


# ── ADMIN ─────────────────────────────────────────────────────────────────────

@routes.get("/api/admin/stats")
async def api_admin_stats(request):
    _, e = require_admin(request)
    if e:
        return e
    return ok(await get_admin_stats())


@routes.get("/api/admin/players")
async def api_admin_players(request):
    _, e = require_admin(request)
    if e:
        return e
    q = request.rel_url.query.get("q", "")
    return ok(await get_all_players(q))


@routes.put("/api/admin/player/{id}")
async def api_admin_player_update(request):
    _, e = require_admin(request)
    if e:
        return e
    try:
        body = await request.json()
    except Exception:
        return err("invalid json")
    return ok(await admin_update_player(int(request.match_info["id"]), body))


@routes.post("/api/admin/tournament")
async def api_admin_create_tour(request):
    _, e = require_admin(request)
    if e:
        return e
    try:
        body = await request.json()
    except Exception:
        return err("invalid json")
    if not body.get("title") or not body.get("start_time"):
        return err("title and start_time required")
    tid = await create_tournament(body)
    return ok({"ok": True, "id": tid})


@routes.delete("/api/admin/tournament/{id}")
async def api_admin_delete_tour(request):
    _, e = require_admin(request)
    if e:
        return e
    await delete_tournament(int(request.match_info["id"]))
    return ok({"ok": True})


@routes.post("/api/admin/tournament/{id}/finish")
async def api_admin_finish_tour(request):
    """Body: { results: [{player_id, place, knockouts, prize}] }"""
    _, e = require_admin(request)
    if e:
        return e
    try:
        body = await request.json()
    except Exception:
        return err("invalid json")
    tid = int(request.match_info["id"])
    for r in body.get("results", []):
        await record_result(
            tid=tid,
            player_id=int(r["player_id"]),
            place=int(r["place"]),
            knockouts=int(r.get("knockouts", 0)),
            prize=float(r.get("prize", 0)),
        )
    await update_tournament_status(tid, "finished")
    return ok({"ok": True})


# ── SERVER ────────────────────────────────────────────────────────────────────

def create_app() -> web.Application:
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_routes(routes)
    static = Path(__file__).parent / "static"
    if static.exists():
        app.router.add_static("/static", static)
    return app


async def run_webapp():
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.WEBAPP_HOST, settings.WEBAPP_PORT)
    await site.start()
    print(f"[WebApp] running on :{settings.WEBAPP_PORT}")
    return runner
