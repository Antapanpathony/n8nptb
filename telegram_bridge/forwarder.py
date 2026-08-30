"""Forwards inbound Telegram messages to n8n's webhook, with retries."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger("telegram_bridge.forwarder")

MAX_ATTEMPTS = 3
BASE_BACKOFF_SECONDS = 1.0


async def forward_to_n8n(webhook_url: str, payload: dict[str, Any]) -> bool:
    """POST payload to n8n, retrying with exponential backoff.

    Never raises: a failure here must not crash the polling loop. Returns
    True on success, False once all attempts are exhausted.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = await client.post(webhook_url, json=payload)
                response.raise_for_status()
                logger.info(
                    "Forwarded message %s to n8n (attempt %d/%d)",
                    payload.get("message_id"),
                    attempt,
                    MAX_ATTEMPTS,
                )
                return True
            except Exception as exc:  # noqa: BLE001 - log and retry, never crash
                logger.warning(
                    "Failed to forward message %s to n8n (attempt %d/%d): %s",
                    payload.get("message_id"),
                    attempt,
                    MAX_ATTEMPTS,
                    exc,
                )
                if attempt < MAX_ATTEMPTS:
                    backoff = BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
                    await asyncio.sleep(backoff)

    logger.error(
        "Giving up forwarding message %s to n8n after %d attempts",
        payload.get("message_id"),
        MAX_ATTEMPTS,
    )
    return False
