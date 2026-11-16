"""GitHub Gist: POST /gists (token needs the `gist` scope)."""
from __future__ import annotations

import httpx

from app.config import reveal
from app.platforms.base import BasePlatform, PlatformError, PublishedPost, api_error


class GitHubGist(BasePlatform):
    name = "GitHub Gist"
    API_URL = "https://api.github.com/gists"

    def credentials(self):
        return {"GITHUB_TOKEN": reveal(self.settings.github_token)}

    async def publish(self, client: httpx.AsyncClient, message: str, link: str) -> PublishedPost:
        response = await client.post(
            self.API_URL,
            json={
                "description": message,
                "public": True,
                "files": {"post.md": {"content": message}},
            },
            headers={
                "Authorization": f"Bearer {reveal(self.settings.github_token)}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        if response.status_code != 201:
            raise api_error(response)
        url = response.json().get("html_url")
        if not url:
            raise PlatformError("GitHub response did not include a gist URL")
        return PublishedPost(url=url)
