"""Runs the Telegram long-polling loop and the local FastAPI server together.

    python -m telegram_bridge
"""

from __future__ import annotations

import asyncio
import logging

import uvicorn

from .api import create_api
from .bot import build_application
from .config import load_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("telegram_bridge")


async def run_bot(application) -> None:
    """Starts the Application and its polling updater, and idles forever."""
    async with application:
        # Long polling and a webhook are mutually exclusive on Telegram's
        # side: if this bot token was ever used with a webhook (e.g. n8n's
        # built-in Telegram Trigger node, which this bridge replaces),
        # getUpdates() fails with "Conflict: can't use getUpdates method
        # while a webhook is active" until the webhook is torn down.
        await application.bot.delete_webhook(drop_pending_updates=True)

        await application.start()
        await application.updater.start_polling(
            allowed_updates=["message"],
            drop_pending_updates=True,
        )
        logger.info("Telegram long polling started")
        try:
            # Idle until cancelled (e.g. Ctrl+C / SIGTERM via task cancellation).
            await asyncio.Event().wait()
        finally:
            await application.updater.stop()
            await application.stop()


async def run_api(application, host: str, port: int) -> None:
    app = create_api(application)
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    logger.info("Bridge API listening on http://%s:%d (localhost only)", host, port)
    await server.serve()


async def main() -> None:
    settings = load_settings()
    application = build_application(settings)

    await asyncio.gather(
        run_bot(application),
        run_api(application, settings.bridge_host, settings.bridge_port),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
