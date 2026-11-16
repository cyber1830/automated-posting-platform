"""Telegram Bot API: sendMessage to a PUBLIC channel (bot must be a channel admin)."""
from __future__ import annotations

import httpx

from app.config import reveal
from app.platforms.base import BasePlatform, PlatformError, PublishedPost


class Telegram(BasePlatform):
    name = "Telegram"

    def credentials(self):
        return {
            "TELEGRAM_BOT_TOKEN": reveal(self.settings.telegram_bot_token),
            "TELEGRAM_CHANNEL_USERNAME": reveal(self.settings.telegram_channel_username),
        }

    async def publish(self, client: httpx.AsyncClient, message: str, link: str) -> PublishedPost:
        username = (reveal(self.settings.telegram_channel_username) or "").lstrip("@")
        token = reveal(self.settings.telegram_bot_token)
        response = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": f"@{username}", "text": message},
        )
        try:
            data = response.json()
        except ValueError:
            data = {}
        # Never build errors from the request URL: it contains the bot token.
        if response.status_code != 200 or not data.get("ok"):
            description = str(data.get("description", "unknown error"))[:200]
            raise PlatformError(f"Telegram rejected the message (HTTP {response.status_code}): {description}")
        message_id = data["result"]["message_id"]
        return PublishedPost(url=f"https://t.me/{username}/{message_id}")
