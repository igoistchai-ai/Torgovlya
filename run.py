import asyncio
import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from urllib.parse import parse_qsl

from aiohttp import web

from bot import APP_URL, SITE_URL, bot, dp, run_analysis
from market import candles

BASE_DIR = Path(__file__).resolve().parent
WEBAPP_DIR = BASE_DIR / "webapp"
WEBAPP_HTML = BASE_DIR / "index.html"
WEBAPP_CSS = BASE_DIR / "app.css"
WEBAPP_JS = BASE_DIR / "app.js"

WEBHOOK_PATH = "/telegram/webhook"
WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")

ALLOWED_SYMBOLS = {
    "BTC/USDT", "ETH/USDT", "LTC/USDT", "SOL/USDT",
    "BNB/USDT", "XRP/USDT", "DOGE/USDT", "ADA/USDT",
}
ALLOWED_TIMEFRAMES = {"1m", "5m", "15m", "1h", "4h", "1d", "1w"}


def json_default(value):
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    raise TypeError(f"Not JSON serializable: {type(value).__name__}")


def telegram_init_data_valid(init_data: str) -> bool:
    """Validate Telegram Mini App initData using the bot token."""
    if not init_data:
        return False

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return False

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return False

    auth_date = pairs.get("auth_date")
    try:
        if auth_date and time.time() - int(auth_date) > 86400:
            return False
    except ValueError:
        return False

    data_check_string = "\n".join(f"{key}={pairs[key]}" for key in sorted(pairs))
    secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    calculated = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(calculated, received_hash)


def api_authorized(request: web.Request) -> bool:
    # Local/browser preview can be enabled explicitly, but production should use Telegram initData.
    if os.getenv("ALLOW_UNAUTH_WEBAPP", "0") == "1":
        return True
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    return telegram_init_data_valid(init_data)


async def health(request: web.Request) -> web.Response:
    return web.Response(text="NEZZX GRAFIK is running")


async def home(request: web.Request) -> web.Response:
    return web.FileResponse(WEBAPP_HTML)


async def telegram_webhook(request: web.Request) -> web.Response:
    if WEBHOOK_SECRET:
        received = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if received != WEBHOOK_SECRET:
            return web.Response(status=403, text="Forbidden")

    try:
        update = await request.json()
        await dp.feed_raw_update(bot, update)
        return web.Response(text="OK")
    except Exception as exc:
        print(f"Webhook error: {exc}", flush=True)
        return web.Response(status=500, text="Webhook error")


async def app_page(request: web.Request) -> web.Response:
    return web.FileResponse(WEBAPP_HTML)


async def app_css(request: web.Request) -> web.Response:
    return web.FileResponse(WEBAPP_CSS)


async def app_js(request: web.Request) -> web.Response:
    return web.FileResponse(WEBAPP_JS)


async def api_candles(request: web.Request) -> web.Response:
    if not api_authorized(request):
        return web.json_response({"error": "Telegram authorization required"}, status=401)

    symbol = request.query.get("symbol", "BTC/USDT")
    timeframe = request.query.get("timeframe", "15m")
    if symbol not in ALLOWED_SYMBOLS or timeframe not in ALLOWED_TIMEFRAMES:
        return web.json_response({"error": "Unsupported symbol or timeframe"}, status=400)

    try:
        df = await asyncio.to_thread(candles, symbol, timeframe)
        rows = []
        for row in df.tail(300).to_dict("records"):
            rows.append({
                "timestamp": row["timestamp"].isoformat() if hasattr(row["timestamp"], "isoformat") else str(row["timestamp"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            })
        return web.json_response({"symbol": symbol, "timeframe": timeframe, "source": "OKX", "candles": rows})
    except Exception as exc:
        print(f"Candles API error: {type(exc).__name__}: {exc}", flush=True)
        return web.json_response({"error": str(exc)[:700]}, status=500)


async def api_analyze(request: web.Request) -> web.Response:
    if not api_authorized(request):
        return web.json_response({"error": "Telegram authorization required"}, status=401)

    try:
        body = await request.json()
    except Exception:
        body = {}

    symbol = str(body.get("symbol", "BTC/USDT"))
    timeframe = str(body.get("timeframe", "15m"))
    if symbol not in ALLOWED_SYMBOLS or timeframe not in ALLOWED_TIMEFRAMES:
        return web.json_response({"error": "Unsupported symbol or timeframe"}, status=400)

    try:
        result = await asyncio.to_thread(run_analysis, symbol, timeframe)
        df = await asyncio.to_thread(candles, symbol, timeframe)
        rows = []
        for row in df.tail(300).to_dict("records"):
            rows.append({
                "timestamp": row["timestamp"].isoformat() if hasattr(row["timestamp"], "isoformat") else str(row["timestamp"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            })
        return web.json_response({"analysis": result, "candles": rows, "source": "OKX"}, dumps=lambda obj: json.dumps(obj, ensure_ascii=False, default=json_default))
    except Exception as exc:
        print(f"Analysis API error: {type(exc).__name__}: {exc}", flush=True)
        return web.json_response({"error": str(exc)[:1000]}, status=500)


async def on_startup(app: web.Application):
    base_url = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
    if not base_url:
        hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()
        if hostname:
            base_url = f"https://{hostname}"

    if base_url:
        webhook_url = f"{base_url}{WEBHOOK_PATH}"
        await bot.set_webhook(
            url=webhook_url,
            secret_token=WEBHOOK_SECRET or None,
            drop_pending_updates=False,
        )
        print(f"Telegram webhook configured: {webhook_url}", flush=True)

        try:
            from aiogram.types import MenuButtonWebApp, WebAppInfo
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="NEZZX GRAFIK",
                    web_app=WebAppInfo(url=f"{base_url}/app"),
                )
            )
            print(f"Telegram Mini App menu configured: {base_url}/app", flush=True)
        except Exception as exc:
            print(f"Menu button setup warning: {type(exc).__name__}: {exc}", flush=True)
    else:
        print("Render URL not found; webhook/menu not configured.", flush=True)


async def on_cleanup(app: web.Application):
    try:
        await bot.delete_webhook(drop_pending_updates=False)
    finally:
        await bot.session.close()


app = web.Application(client_max_size=2 * 1024 * 1024)
app.router.add_get("/", home)
app.router.add_get("/health", health)
app.router.add_get("/healthz", health)
app.router.add_post(WEBHOOK_PATH, telegram_webhook)
app.router.add_get("/app", app_page)
app.router.add_get("/app/", app_page)
app.router.add_get("/app/style.css", app_css)
app.router.add_get("/app/app.css", app_css)
app.router.add_get("/app/app.js", app_js)
app.router.add_get("/api/candles", api_candles)
app.router.add_post("/api/analyze", api_analyze)
app.on_startup.append(on_startup)
app.on_cleanup.append(on_cleanup)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    print(f"HTTP server listening on 0.0.0.0:{port}", flush=True)
    web.run_app(app, host="0.0.0.0", port=port)
