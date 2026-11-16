"""Fan-out service: posts to every platform concurrently, isolating failures."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from app.platforms.base import BasePlatform, PlatformError
from app.schemas import PlatformResult
from app.validators import extract_link

logger = logging.getLogger("posting")


def _failed(name: str, error: str) -> PlatformResult:
    return PlatformResult(platform=name, status="failed", public_access=False, error=error)


class PostingService:
    def __init__(
        self,
        platforms: list[BasePlatform],
        client: httpx.AsyncClient,
        platform_timeout: float = 30.0,
        verify_public: bool = True,
    ) -> None:
        self.platforms = platforms
        self.client = client
        self.platform_timeout = platform_timeout
        self.verify_public = verify_public

    async def publish_all(self, message: str) -> list[PlatformResult]:
        link = extract_link(message)
        # _publish_one never raises, so one platform can't take down the others.
        return list(
            await asyncio.gather(*(self._publish_one(p, message, link) for p in self.platforms))
        )

    async def _publish_one(self, platform: BasePlatform, message: str, link: str) -> PlatformResult:
        missing = platform.missing_credentials()
        if missing:
            return _failed(platform.name, f"Missing credentials: {', '.join(missing)}")

        try:
            post = await asyncio.wait_for(
                platform.publish(self.client, message, link), timeout=self.platform_timeout
            )
        except PlatformError as exc:
            return _failed(platform.name, str(exc))
        except asyncio.TimeoutError:
            return _failed(platform.name, f"Timed out after {self.platform_timeout:g}s")
        except httpx.TimeoutException:
            return _failed(platform.name, "Request to the platform timed out")
        except httpx.HTTPError as exc:
            # Type name only: httpx messages can embed request URLs (Telegram: bot token).
            return _failed(platform.name, f"Network error: {type(exc).__name__}")
        except Exception as exc:  # noqa: BLE001 - last line of defence, must not escape
            logger.exception("Unexpected error while posting to %s", platform.name)
            return _failed(platform.name, f"Unexpected error: {type(exc).__name__}")

        posted_at = datetime.now(timezone.utc)
        public = post.public_access
        if public is None:
            public = await self._verify(platform, post) if self.verify_public else False

        return PlatformResult(
            platform=platform.name,
            status="success",
            posted_url=post.url,
            public_access=public,
            date=posted_at.strftime("%Y-%m-%d"),
            time=posted_at.strftime("%H:%M:%S"),
            error=None,
        )

    async def _verify(self, platform: BasePlatform, post) -> bool:
        # A failed verification must never turn a successful post into a failure.
        try:
            return await asyncio.wait_for(
                platform.check_public(self.client, post), timeout=self.platform_timeout
            )
        except Exception:  # noqa: BLE001
            return False
