"""Registered posting platforms."""
from __future__ import annotations

from app.config import Settings
from app.platforms.base import BasePlatform
from app.platforms.bluesky import Bluesky
from app.platforms.devto import DevTo
from app.platforms.github_gist import GitHubGist
from app.platforms.telegram import Telegram
from app.platforms.telegraph import Telegraph

PLATFORM_CLASSES: list[type[BasePlatform]] = [
    DevTo,
    Telegraph,
    Bluesky,
    GitHubGist,
    Telegram,
]


def build_platforms(settings: Settings) -> list[BasePlatform]:
    return [cls(settings) for cls in PLATFORM_CLASSES]
