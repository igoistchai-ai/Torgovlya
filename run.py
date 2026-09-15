import os

from aiohttp import web

from bot import bot, dp

WEBHOOK_PATH = "/telegram/webhook"
WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")


async def health(request: web.Request) -> web.Response:
    return web.json_response({
        "status": "ok",
        "service": "crypto-vision-analyst",
    })


async def telegram_webhook(request: web.Request) -> web.Response:
    if WEBHOOK_SECRET:
        received = request.headers.get(
            "X-Telegram-Bot-Api-Secret-Token", ""
        )
        if received != WEBHOOK_SECRET:
            return web.Response(status=403, text="Forbidden")

    try:
        update = await request.json()
        await dp.feed_raw_update(bot, update)
        return web.Response(text="OK")
    except Exception as exc:
        print(f"Webhook update error: {type(exc).__name__}: {exc}", flush=True)
        # Return 200 after receiving the update so Telegram does not hammer
        # the endpoint repeatedly when a handler itself has an error.
        return web.Response(text="OK")


async def on_startup(app: web.Application):
    external_url = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
    hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()

    if external_url:
        base_url = external_url
    elif hostname:
        base_url = f"https://{hostname}"
    else:
        print(
            "Render URL is not available; Telegram webhook was not configured.",
            flush=True,
        )
        return

    webhook_url = f"{base_url}{WEBHOOK_PATH}"

    try:
        current = await bot.get_webhook_info()
        print(
            f"Previous Telegram webhook: {current.url or 'none'}",
            flush=True,
        )

        await bot.set_webhook(
            url=webhook_url,
            secret_token=WEBHOOK_SECRET or None,
            drop_pending_updates=False,
            allowed_updates=dp.resolve_used_update_types(),
        )

        info = await bot.get_webhook_info()
        print(
            f"Telegram webhook configured: {info.url}",
            flush=True,
        )
        print(
            f"Pending updates: {info.pending_update_count}",
            flush=True,
        )
    except Exception as exc:
        print(
            f"Telegram webhook setup error: {type(exc).__name__}: {exc}",
            flush=True,
        )
        raise


async def on_cleanup(app: web.Application):
    # Do NOT delete the webhook on Render shutdown/redeploy.
    # Telegram can continue targeting the same stable Render URL.
    try:
        await bot.session.close()
    except Exception as exc:
        print(f"Telegram session cleanup error: {exc}", flush=True)


app = web.Application(client_max_size=10 * 1024 * 1024)
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
