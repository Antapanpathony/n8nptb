"""Local-only FastAPI app that lets n8n send Telegram messages.

Mirrors the operations n8n's built-in Telegram node exposes for outbound
messages (send text/photo/document, edit a message, parse mode, reply
threading, inline keyboards) so a workflow built against that node needs
only to swap it for the Telegram Bridge node — same fields, same behavior.

Bound to 127.0.0.1 by the caller (see __main__.py) — never exposed publicly.
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, model_validator
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application

logger = logging.getLogger("telegram_bridge.api")

Operation = Literal["sendMessage", "sendPhoto", "sendDocument", "editMessageText"]


class ReplyMarkup(BaseModel):
    """Telegram's InlineKeyboardMarkup shape: rows of buttons."""

    inline_keyboard: list[list[dict]]


class SendMessageRequest(BaseModel):
    operation: Operation = "sendMessage"
    chat_id: int | str

    text: str | None = None
    photo_path: str | None = None
    document_path: str | None = None
    caption: str | None = None

    # Required for editMessageText.
    message_id: int | None = None

    # Optional fields mirroring n8n's native Telegram node.
    parse_mode: Literal["Markdown", "MarkdownV2", "HTML"] | None = None
    disable_notification: bool | None = None
    reply_to_message_id: int | None = None
    reply_markup: ReplyMarkup | None = None

    @model_validator(mode="after")
    def _check_payload(self) -> "SendMessageRequest":
        if self.operation == "sendMessage" and not self.text:
            raise ValueError("'text' is required for sendMessage.")
        if self.operation == "sendPhoto" and not self.photo_path:
            raise ValueError("'photo_path' is required for sendPhoto.")
        if self.operation == "sendDocument" and not self.document_path:
            raise ValueError("'document_path' is required for sendDocument.")
        if self.operation == "editMessageText":
            if not self.message_id:
                raise ValueError("'message_id' is required for editMessageText.")
            if not self.text:
                raise ValueError("'text' is required for editMessageText.")
        return self


def _build_reply_markup(reply_markup: ReplyMarkup | None) -> InlineKeyboardMarkup | None:
    if reply_markup is None:
        return None
    rows = [
        [InlineKeyboardButton(**button) for button in row]
        for row in reply_markup.inline_keyboard
    ]
    return InlineKeyboardMarkup(rows)


def create_api(application: Application) -> FastAPI:
    app = FastAPI(title="telegram-bridge", version="0.1.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/send")
    async def send(request: SendMessageRequest) -> dict[str, object]:
        bot = application.bot
        markup = _build_reply_markup(request.reply_markup)

        try:
            if request.operation == "sendPhoto":
                with open(request.photo_path, "rb") as photo_file:
                    message = await bot.send_photo(
                        chat_id=request.chat_id,
                        photo=photo_file,
                        caption=request.caption,
                        parse_mode=request.parse_mode,
                        disable_notification=request.disable_notification,
                        reply_to_message_id=request.reply_to_message_id,
                        reply_markup=markup,
                    )
            elif request.operation == "sendDocument":
                with open(request.document_path, "rb") as document_file:
                    message = await bot.send_document(
                        chat_id=request.chat_id,
                        document=document_file,
                        caption=request.caption,
                        parse_mode=request.parse_mode,
                        disable_notification=request.disable_notification,
                        reply_to_message_id=request.reply_to_message_id,
                        reply_markup=markup,
                    )
            elif request.operation == "editMessageText":
                message = await bot.edit_message_text(
                    chat_id=request.chat_id,
                    message_id=request.message_id,
                    text=request.text,
                    parse_mode=request.parse_mode,
                    reply_markup=markup,
                )
            else:  # sendMessage
                message = await bot.send_message(
                    chat_id=request.chat_id,
                    text=request.text,
                    parse_mode=request.parse_mode,
                    disable_notification=request.disable_notification,
                    reply_to_message_id=request.reply_to_message_id,
                    reply_markup=markup,
                )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 - surface as a clean 502
            logger.exception("Failed to send Telegram message")
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        # edit_message_text returns a bool (not a Message) when editing an
        # inline message the bot didn't send itself; that path isn't
        # reachable via chat_id+message_id, but guard it anyway.
        message_id = getattr(message, "message_id", request.message_id)
        return {"ok": True, "message_id": message_id}

    return app
