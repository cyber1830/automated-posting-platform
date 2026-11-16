"""DEV.to (Forem API v1): https://developers.forem.com/api/v1#tag/articles"""
from __future__ import annotations

import httpx

from app.config import reveal
from app.platforms.base import BasePlatform, PlatformError, PublishedPost, api_error, make_title
from datetime import datetime, timezone



class DevTo(BasePlatform):
    name = "DEV.to"
    API_URL = "https://dev.to/api/articles"

    def credentials(self):
        return {"DEVTO_API_KEY": reveal(self.settings.devto_api_key)}

    async def publish(self, client: httpx.AsyncClient, message: str, link: str) -> PublishedPost:
        payload = {
            "article": {
                "title": f"{make_title(message, link)} ({datetime.now(timezone.utc):%H:%M:%S})",
                "body_markdown": message,
                "published": True,
            }
        }
        response = await client.post(
            self.API_URL,
            json=payload,
            headers={
                "api-key": reveal(self.settings.devto_api_key) or "",
                "Accept": "application/vnd.forem.api-v1+json",
            },
        )
        if response.status_code not in (200, 201):
            raise api_error(response)
        url = response.json().get("url")
        if not url:
            raise PlatformError("DEV.to response did not include an article URL")
        return PublishedPost(url=url)
