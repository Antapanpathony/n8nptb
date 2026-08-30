"""Telegram long-polling side of the bridge.

Builds the python-telegram-bot Application, wires up handlers for text,
photo, and document messages, and forwards each incoming update to n8n as
JSON over HTTP (localhost only).

The payload forwarded to n8n is the raw Telegram Bot API Update object
(``update.to_dict()``) — the same shape n8n's built-in Telegram Trigger node
delivers as ``$json.body`` when it receives a webhook from Telegram. That
means workflows written against the native node's expressions
(``{{$json.body.message.chat.id}}``, ``{{$json.body.message.from.username}}``,
``{{$json.body.message.text}}``, etc.) work unmodified against this bridge.
The one addition is a ``bridge`` key holding the locally downloaded file
path/type for photos and documents, since Telegram's Update object itself
only carries a ``file_id`` — it never resolves to a path on disk.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from telegram import Update
from telegram.ext import (
    Application,
    ContextTypes,
    MessageHandler,
    filters,
)

from .config import Settings
from .forwarder import forward_to_n8n

logger = logging.getLogger("telegram_bridge.bot")


async def _download_attachment(
    context: ContextTypes.DEFAULT_TYPE,
    file_id: str,
    incoming_dir: Path,
    suggested_name: str | None,
) -> str:
    """Downloads a Telegram file to incoming_dir and returns the local path."""
    telegram_file = await context.bot.get_file(file_id)
    incoming_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(telegram_file.file_path or "").suffix if telegram_file.file_path else ""
    filename = suggested_name or f"{file_id}{ext}"
    # Keep filenames unique even if Telegram reuses a document's original name.
    filename = f"{int(time.time())}_{filename}"

    local_path = incoming_dir / filename
    await telegram_file.download_to_drive(custom_path=str(local_path))
    return str(local_path)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    message = update.effective_message
    if message is None:
        return

    logger.info(
        "Received message %s from chat %s", message.message_id, message.chat_id
    )

    # Same shape as the raw JSON Telegram POSTs to a webhook — this is what
    # n8n's built-in Telegram Trigger node hands workflows as $json.body.
    payload: dict[str, Any] = update.to_dict()
    bridge_extra: dict[str, Any] = {"file_path": None, "file_type": None}

    try:
        incoming_dir = Path(settings.incoming_dir)

        if message.photo:
            # Largest photo is last in the list.
            photo = message.photo[-1]
            bridge_extra["file_path"] = await _download_attachment(
                context, photo.file_id, incoming_dir, f"{photo.file_unique_id}.jpg"
            )
            bridge_extra["file_type"] = "photo"
        elif message.document:
            bridge_extra["file_path"] = await _download_attachment(
                context,
                message.document.file_id,
                incoming_dir,
                message.document.file_name,
            )
            bridge_extra["file_type"] = "document"
    except Exception:  # noqa: BLE001 - never let a download failure crash polling
        logger.exception(
            "Failed to download attachment for message %s", message.message_id
        )

    payload["bridge"] = bridge_extra

    await forward_to_n8n(settings.n8n_webhook_url, payload)


def build_application(settings: Settings) -> Application:
    application = (
        Application.builder()
        .token(settings.bot_token)
        .build()
    )
    application.bot_data["settings"] = settings

    application.add_handler(
        MessageHandler(
            filters.PHOTO | filters.TEXT | filters.Document.ALL,
            handle_message,
        )
    )

    return application
