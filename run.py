import os

from aiohttp import web

from bot import bot, dp


WEBHOOK_PATH = "/telegram/webhook"
WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")


async def health(request: web.Request) -> web.Response:
    return web.Response(text="Crypto Vision Analyst is running")


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


async def on_startup(app: web.Application):
    external_url = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
    hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()
    if external_url:
        base_url = external_url
    elif hostname:
        base_url = f"https://{hostname}"
    else:
        # Local mode: webhook is not configured; run.py can still expose health.
        print("RENDER_EXTERNAL_URL/RENDER_EXTERNAL_HOSTNAME not found; webhook not configured.", flush=True)
        return

    webhook_url = f"{base_url}{WEBHOOK_PATH}"
    await bot.set_webhook(
        url=webhook_url,
        secret_token=WEBHOOK_SECRET or None,
        drop_pending_updates=False,
    )
    print(f"Telegram webhook configured: {webhook_url}", flush=True)


async def on_cleanup(app: web.Application):
    try:
        await bot.delete_webhook(drop_pending_updates=False)
    finally:
        await bot.session.close()


app = web.Application()
app.router.add_get("/", health)
app.router.add_get("/health", health)
app.router.add_get("/healthz", health)
app.router.add_post(WEBHOOK_PATH, telegram_webhook)
app.on_startup.append(on_startup)
app.on_cleanup.append(on_cleanup)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    print(f"HTTP server listening on 0.0.0.0:{port}", flush=True)
    web.run_app(app, host="0.0.0.0", port=port)
