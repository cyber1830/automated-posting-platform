"""Platform abstraction: every integration implements BasePlatform."""
from __future__ import annotations

import asyncio
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import httpx

from app.config import Settings


class PlatformError(Exception):
    """An expected, user-presentable failure (bad token, API rejected the post...)."""


@dataclass
class PublishedPost:
    url: str
    # None -> the service verifies public access itself via check_public().
    public_access: bool | None = None
    meta: dict[str, str] = field(default_factory=dict)


def api_error(response: httpx.Response) -> PlatformError:
    """Turn a non-2xx response into a short, secret-free PlatformError."""
    detail = ""
    try:
        data = response.json()
        if isinstance(data, dict):
            detail = str(
                data.get("message")
                or data.get("error_description")
                or data.get("error")
                or data.get("description")
                or data.get("errors")
                or ""
            )
    except ValueError:
        detail = response.text
    detail = " ".join(detail.split())[:200]
    reason = {401: "Authentication failed", 403: "Forbidden", 429: "Rate limited"}.get(
        response.status_code, "Request rejected"
    )
    return PlatformError(
        f"{reason} (HTTP {response.status_code})" + (f": {detail}" if detail else "")
    )


def make_title(message: str, link: str, limit: int = 80) -> str:
    """Derive a post title from the message (link removed, whitespace collapsed)."""
    text = " ".join(message.replace(link, "").split()).strip(" -:,.")
    text = re.sub(r"\s+", " ", text)
    return (text[:limit].rstrip() or "Check this out")


class BasePlatform(ABC):
    name: str = "base"
    public_check_attempts = 3
    public_check_delay = 1.0  # seconds between attempts (content may lag briefly)

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abstractmethod
    def credentials(self) -> dict[str, str | None]:
        """Map of ENV_VAR_NAME -> value (None/empty when missing)."""

    def missing_credentials(self) -> list[str]:
        return [key for key, value in self.credentials().items() if not value]

    @property
    def is_configured(self) -> bool:
        return not self.missing_credentials()

    @abstractmethod
    async def publish(
        self, client: httpx.AsyncClient, message: str, link: str
    ) -> PublishedPost:
        """Publish the message. Raise PlatformError (or let httpx errors bubble up)."""

    async def check_public(self, client: httpx.AsyncClient, post: PublishedPost) -> bool:
        """Verify, without credentials, that the published content is reachable."""
        for attempt in range(self.public_check_attempts):
            if attempt:
                await asyncio.sleep(self.public_check_delay)
            if await self._probe(client, post):
                return True
        return False

    async def _probe(self, client: httpx.AsyncClient, post: PublishedPost) -> bool:
        try:
            response = await client.get(post.url, follow_redirects=True)
        except httpx.HTTPError:
            return False
        return response.status_code == 200
