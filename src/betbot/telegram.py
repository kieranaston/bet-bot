"""Minimal Telegram Bot API client -- just HTTP calls, no long-running polling.

We use getUpdates in short-poll mode (called once per scheduled run, with an offset stored
in the DB) rather than python-telegram-bot's polling loop, because this bot runs as a
periodic GitHub Actions job, not a persistent process. See betbot.commands for how incoming
messages are turned into actions.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import requests

logger = logging.getLogger(__name__)


@dataclass
class TelegramClient:
    bot_token: str
    chat_id: str

    @property
    def _base_url(self) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}"

    def send_message(self, text: str, parse_mode: str | None = "Markdown") -> bool:
        payload: dict[str, Any] = {
            "chat_id": self.chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        resp = requests.post(f"{self._base_url}/sendMessage", json=payload, timeout=15)
        if resp.status_code == 200:
            return True
        logger.error("Telegram sendMessage failed: %s", resp.text[:500])
        # Legacy Markdown is brittle ([brackets], underscores in team names, etc.). A parse
        # failure would otherwise swallow the reply entirely -- retry as plain text.
        if parse_mode:
            return self.send_message(text, parse_mode=None)
        return False

    def delete_webhook(self) -> bool:
        """Polling via getUpdates fails with HTTP 409 while a webhook is registered."""
        resp = requests.post(
            f"{self._base_url}/deleteWebhook",
            json={"drop_pending_updates": False},
            timeout=15,
        )
        if resp.status_code != 200:
            logger.error("Telegram deleteWebhook failed: %s", resp.text[:500])
            return False
        return True

    def get_updates(self, offset: int | None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"timeout": 0}
        if offset is not None:
            params["offset"] = offset
        resp = requests.get(f"{self._base_url}/getUpdates", params=params, timeout=15)
        if resp.status_code == 409:
            logger.warning(
                "Telegram getUpdates conflict (webhook still set?); deleting webhook and retrying"
            )
            self.delete_webhook()
            resp = requests.get(f"{self._base_url}/getUpdates", params=params, timeout=15)
        if resp.status_code != 200:
            logger.error("Telegram getUpdates failed: %s", resp.text[:500])
            return []
        return resp.json().get("result", [])
