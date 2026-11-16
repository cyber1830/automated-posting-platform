"""Telegraph API: create a public page."""
from __future__ import annotations

import httpx
import json

from app.config import reveal
from app.platforms.base import BasePlatform, PlatformError, PublishedPost, make_title


class Telegraph(BasePlatform):
    name = "Telegraph"
    API_URL = "https://api.telegra.ph/createPage"

    def credentials(self):
        return {"TELEGRAPH_ACCESS_TOKEN": reveal(self.settings.telegraph_access_token)}

    async def publish(self, client: httpx.AsyncClient, message: str, link: str) -> PublishedPost:
        response = await client.post(
            self.API_URL,
            data={
                "access_token": reveal(self.settings.telegraph_access_token),
                "title": make_title(message, link),
                "content": json.dumps([{"tag": "p", "children": [message]}]),
            },
        )
        try:
            body = response.json()
        except ValueError:
            raise PlatformError("Telegraph returned a non-JSON response") from None
        if response.status_code != 200 or not body.get("ok"):
            raise PlatformError(f"Telegraph rejected the post: {body.get('error', 'Unknown error')}")
        try:
            return PublishedPost(url=body["result"]["url"])
        except (KeyError, TypeError):
            raise PlatformError("Telegraph response did not include a page URL") from None
