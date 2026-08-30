"""Local-only FastAPI app that lets n8n send Telegram messages.

Bound to 127.0.0.1 by the caller (see __main__.py) — never exposed publicly.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, model_validator
from telegram.ext import Application

logger = logging.getLogger("telegram_bridge.api")


class SendMessageRequest(BaseModel):
    chat_id: int | str
    text: str | None = None
    photo_path: str | None = None
    caption: str | None = None

    @model_validator(mode="after")
    def _check_payload(self) -> "SendMessageRequest":
        if not self.text and not self.photo_path:
            raise ValueError("Provide either 'text' or 'photo_path'.")
        return self


def create_api(application: Application) -> FastAPI:
    app = FastAPI(title="telegram-bridge", version="0.1.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/send")
    async def send(request: SendMessageRequest) -> dict[str, object]:
        bot = application.bot
        try:
            if request.photo_path:
                with open(request.photo_path, "rb") as photo_file:
                    message = await bot.send_photo(
                        chat_id=request.chat_id,
                        photo=photo_file,
                        caption=request.caption,
                    )
            else:
                message = await bot.send_message(
                    chat_id=request.chat_id,
                    text=request.text,
                )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 - surface as a clean 502
            logger.exception("Failed to send Telegram message")
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        return {"ok": True, "message_id": message.message_id}

    return app
