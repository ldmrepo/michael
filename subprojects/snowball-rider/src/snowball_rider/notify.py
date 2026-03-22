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
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"},
            timeout=10,
        )
        return r.status_code == 200
    except Exception as e:
        logger.error("Telegram send failed: %s", e)
        return False
