"""Configuration loaded from environment / .env."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    n8n_webhook_url: str
    bridge_host: str
    bridge_port: int
    incoming_dir: str


def load_settings() -> Settings:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError(
            "BOT_TOKEN is not set. Copy .env.example to .env and fill it in."
        )

    n8n_webhook_url = os.getenv(
        "N8N_WEBHOOK_URL", "http://localhost:5678/webhook/telegram-in"
    ).strip()

    # The bridge must never listen on anything but loopback: it is not
    # designed to be reachable from outside this machine.
    bridge_host = "127.0.0.1"
    bridge_port = int(os.getenv("BRIDGE_PORT", "8811"))

    incoming_dir = os.getenv("INCOMING_DIR", "./incoming")

    return Settings(
        bot_token=bot_token,
        n8n_webhook_url=n8n_webhook_url,
        bridge_host=bridge_host,
        bridge_port=bridge_port,
        incoming_dir=incoming_dir,
    )
