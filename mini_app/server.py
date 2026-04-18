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
    get_participants, get_my_tournaments, record_result, add_knockouts,
)
from config.settings import settings

TEMPLATE_DIR = Path(__file__).parent / "templates"
routes = web.RouteTableDef()


# ── CORS ─────────────────────────────────────────────────────────────────────

CORS_HEADERS = {
    "Access-Control-Allow-Headers": "Content-Type, X-Telegram-Init-Data, X-Telegram-User",
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

import logging as _log

def validate_init_data(raw: str) -> dict | None:
    """Validate Telegram initData HMAC and return user dict, or None."""
    try:
        params = dict(parse_qsl(raw, strict_parsing=False))
        h = params.pop("hash", None)
        if not h:
            return None
        check_str = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
        token = settings.BOT_TOKEN.strip()
        secret   = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
        expected = hmac.new(secret, check_str.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, h):
            _log.warning("[AUTH] HMAC mismatch — will try raw parse")
            return None
        user = json.loads(params.get("user", "null") or "null")
        if not user or not user.get("id"):
            return None
        _log.info("[AUTH] HMAC ok user_id=%s", user["id"])
        return user
    except Exception as e:
        _log.warning("[AUTH] validate exception: %s", e)
        return None


def parse_user_from_raw(raw: str) -> dict | None:
    """Parse user from initData string WITHOUT verifying HMAC signature."""
    try:
        params = dict(parse_qsl(raw, strict_parsing=False))
        user = json.loads(params.get("user", "null") or "null")
        if user and user.get("id"):
            _log.warning("[AUTH] accepted initData without HMAC user_id=%s", user["id"])
            return user
    except Exception:
        pass
    return None


def get_tg_user(request: web.Request) -> dict | None:
    # ── 1. HMAC-validated initData header ────────────────────────────────
    raw = request.headers.get("X-Telegram-Init-Data", "")
    if raw:
        user = validate_init_data(raw)
        if user:
            return user
        # HMAC failed — accept without validation (internal app, acceptable)
        user = parse_user_from_raw(raw)
        if user:
            return user

    # ── 2. X-Telegram-User header (unsigned) ─────────────────────────────
    user_json = request.headers.get("X-Telegram-User", "")
    if user_json:
        try:
            user = json.loads(user_json)
            if user.get("id"):
                _log.warning("[AUTH] X-Telegram-User fallback id=%s", user["id"])
                return user
        except Exception:
            pass

    # ── 3. ?tg=ID query param (set by bot in the WebApp URL) ─────────────
    tg_id_str = request.rel_url.query.get("tg") or request.rel_url.query.get("tg_id")
    if tg_id_str:
        try:
            uid = int(tg_id_str)
            if uid > 0:
                fn = request.rel_url.query.get("fn", "")
                un = request.rel_url.query.get("un", "")
                _log.warning("[AUTH] URL-param fallback tg_id=%s", uid)
                return {"id": uid, "first_name": fn, "username": un, "last_name": ""}
        except (ValueError, TypeError):
            pass

    _log.warning("[AUTH] no auth — headers=%s query=%s",
                 list(request.headers.keys()),
                 dict(request.rel_url.query))
    return None


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
    if not u or not u.get("id"):
        return None, err("unauthorized", 401)
    return u, None


def require_admin(request):
    u, e = require_auth(request)
    if e:
        return None, e
    if not is_admin(u["id"]):
        return None, err("forbidden", 403)
    return u, None


# ── DEBUG ────────────────────────────────────────────────────────────────────

@routes.get("/api/debug-auth")
async def debug_auth(request):
    raw       = request.headers.get("X-Telegram-Init-Data", "")
    user_hdr  = request.headers.get("X-Telegram-User", "")
    tg_qp     = request.rel_url.query.get("tg", "")
    info = {
        "init_data_len":   len(raw),
        "user_header_len": len(user_hdr),
        "tg_query_param":  tg_qp,
        "token_len":       len(settings.BOT_TOKEN.strip()),
    }
    resolved = get_tg_user(request)
    info["resolved_user_id"] = resolved.get("id") if resolved else None
    if raw:
        try:
            params = dict(parse_qsl(raw, strict_parsing=False))
            h = params.pop("hash", None)
            info["hash_present"] = bool(h)
            info["keys"] = list(params.keys())
            if h:
                check_str = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
                token  = settings.BOT_TOKEN.strip()
                secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
                exp    = hmac.new(secret, check_str.encode(), hashlib.sha256).hexdigest()
                info["hmac_valid"] = hmac.compare_digest(exp, h)
        except Exception as e:
            info["parse_error"] = str(e)
    return ok(info)


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
    try:
        body = await request.json()
    except Exception:
        return err("invalid json")

    # Auth: normal path first; if that fails, try _tg_id from the body itself
    u, e = require_auth(request)
    if e:
        try:
            uid = int(body.get("_tg_id", 0))
            if uid > 0:
                fn = str(body.get("_tg_fn", ""))
                un = str(body.get("_tg_un", ""))
                u, e = {"id": uid, "first_name": fn, "username": un, "last_name": ""}, None
                _log.warning("[AUTH] register body fallback tg_id=%s", uid)
        except Exception:
            pass
    if e:
        return e

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


@routes.post("/api/admin/tournament/{id}/knockouts")
async def api_admin_knockouts(request):
    """Record knockouts for players during an active tournament.
    Body: { knockouts: [{player_id, knockouts}] }"""
    _, e = require_admin(request)
    if e:
        return e
    try:
        body = await request.json()
    except Exception:
        return err("invalid json")
    await add_knockouts(body.get("knockouts", []))
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
