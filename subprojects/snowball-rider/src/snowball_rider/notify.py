"""Telegram notification."""

from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)

BOT_TOKEN = ""
CHAT_ID = ""


def _load() -> None:
    global BOT_TOKEN, CHAT_ID
    BOT_TOKEN = os.environ.get("SCALPER_BOT_TOKEN", "")
    CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def send(message: str) -> bool:
    if not BOT_TOKEN:
        _load()
    if not BOT_TOKEN or not CHAT_ID:
        return False
    import time
    for attempt in range(3):
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"},
                timeout=10,
            )
            if r.status_code == 200:
                return True
        except Exception as e:
            logger.error("Telegram send failed (attempt %d): %s", attempt + 1, e)
        if attempt < 2:
            time.sleep(2)
    return False
