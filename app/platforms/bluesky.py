"""Bluesky (AT Protocol): createSession -> com.atproto.repo.createRecord."""
from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.config import reveal
from app.platforms.base import BasePlatform, PlatformError, PublishedPost, api_error

PDS = "https://bsky.social"
PUBLIC_API = "https://public.api.bsky.app"


def build_link_facets(text: str, link: str) -> list[dict]:
    """Make the link clickable. Facet offsets are UTF-8 *byte* offsets."""
    raw, needle = text.encode("utf-8"), link.encode("utf-8")
    start = raw.find(needle)
    if start < 0:
        return []
    return [
        {
            "index": {"byteStart": start, "byteEnd": start + len(needle)},
            "features": [{"$type": "app.bsky.richtext.facet#link", "uri": link}],
        }
    ]


class Bluesky(BasePlatform):
    name = "Bluesky"

    def credentials(self):
        return {
            "BLUESKY_IDENTIFIER": reveal(self.settings.bluesky_identifier),
            "BLUESKY_APP_PASSWORD": reveal(self.settings.bluesky_app_password),
        }

    async def publish(self, client: httpx.AsyncClient, message: str, link: str) -> PublishedPost:
        session = await client.post(
            f"{PDS}/xrpc/com.atproto.server.createSession",
            json={
                "identifier": reveal(self.settings.bluesky_identifier),
                "password": reveal(self.settings.bluesky_app_password),
            },
        )
        if session.status_code != 200:
            raise api_error(session)
        session_data = session.json()

        record = {
            "$type": "app.bsky.feed.post",
            "text": message,  # limit is 300 graphemes; our input cap is 200 chars
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "facets": build_link_facets(message, link),
        }
        created = await client.post(
            f"{PDS}/xrpc/com.atproto.repo.createRecord",
            json={
                "repo": session_data["did"],
                "collection": "app.bsky.feed.post",
                "record": record,
            },
            headers={"Authorization": f"Bearer {session_data['accessJwt']}"},
        )
        if created.status_code != 200:
            raise api_error(created)
        at_uri = created.json().get("uri")
        if not at_uri:
            raise PlatformError("Bluesky response did not include a post URI")
        rkey = at_uri.rsplit("/", 1)[-1]
        handle = session_data.get("handle") or session_data["did"]
        return PublishedPost(
            url=f"https://bsky.app/profile/{handle}/post/{rkey}",
            meta={"at_uri": at_uri},
        )

    async def _probe(self, client: httpx.AsyncClient, post: PublishedPost) -> bool:
        # bsky.app is a SPA that returns 200 for anything, so ask the public API.
        try:
            response = await client.get(
                f"{PUBLIC_API}/xrpc/app.bsky.feed.getPosts",
                params={"uris": post.meta.get("at_uri", "")},
            )
            return response.status_code == 200 and bool(response.json().get("posts"))
        except (httpx.HTTPError, ValueError):
            return False
