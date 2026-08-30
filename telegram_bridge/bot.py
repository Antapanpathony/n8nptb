"""Telegram long-polling side of the bridge.

Builds the python-telegram-bot Application, wires up handlers for text,
photo, and document messages, and forwards each incoming message to n8n as
JSON over HTTP (localhost only).
"""

from __future__ import annotations

import logging
import os
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


def _sender_info(update: Update) -> dict[str, Any]:
    user = update.effective_user
    if user is None:
        return {}
    return {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }


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

    payload: dict[str, Any] = {
        "chat_id": message.chat_id,
        "message_id": message.message_id,
        "date": message.date.isoformat() if message.date else None,
        "from": _sender_info(update),
        "text": message.text,
        "caption": message.caption,
        "file_path": None,
        "file_type": None,
    }

    try:
        incoming_dir = Path(settings.incoming_dir)

        if message.photo:
            # Largest photo is last in the list.
            photo = message.photo[-1]
            payload["file_path"] = await _download_attachment(
                context, photo.file_id, incoming_dir, f"{photo.file_unique_id}.jpg"
            )
            payload["file_type"] = "photo"
        elif message.document:
            payload["file_path"] = await _download_attachment(
                context,
                message.document.file_id,
                incoming_dir,
                message.document.file_name,
            )
            payload["file_type"] = "document"
    except Exception:  # noqa: BLE001 - never let a download failure crash polling
        logger.exception(
            "Failed to download attachment for message %s", message.message_id
        )

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
