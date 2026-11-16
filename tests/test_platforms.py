"""Adapter tests against mocked HTTP (httpx.MockTransport). No network needed."""
import asyncio
import json

import httpx
import pytest

from app.config import Settings
from app.platforms.base import PlatformError, PublishedPost, make_title
from app.platforms.bluesky import Bluesky, build_link_facets
from app.platforms.devto import DevTo
from app.platforms.github_gist import GitHubGist
from app.platforms.telegraph import Telegraph
from app.platforms.telegram import Telegram

LINK = "https://example.com"
MSG = f"Héllo wörld, grow online. {LINK}"


def client_for(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def run(platform, handler, message=MSG, link=LINK):
    async def go():
        async with client_for(handler) as client:
            return await platform.publish(client, message, link)

    return asyncio.run(go())


def cfg(**kw):
    return Settings(_env_file=None, **kw)


def test_make_title_removes_link_and_truncates():
    assert make_title(f"Hello there {LINK}", LINK) == "Hello there"
    assert make_title(LINK, LINK) == "Check this out"
    assert len(make_title("w " * 100 + LINK, LINK)) <= 80


def test_devto_payload_and_url():
    seen = {}

    def handler(request):
        seen["key"] = request.headers["api-key"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json={"url": "https://dev.to/me/post-1"})

    post = run(DevTo(cfg(devto_api_key="k")), handler)
    assert post.url == "https://dev.to/me/post-1"
    assert seen["key"] == "k"
    assert seen["body"]["article"]["published"] is True


def test_devto_auth_failure():
    handler = lambda r: httpx.Response(401, json={"error": "unauthorized", "status": 401})
    with pytest.raises(PlatformError, match="Authentication failed.*401"):
        run(DevTo(cfg(devto_api_key="bad")), handler)


def test_telegraph_success():
    handler = lambda r: httpx.Response(200, json={"ok": True, "result": {"url": "https://telegra.ph/hello-01-01"}})
    settings = cfg(telegraph_access_token="t")
    assert run(Telegraph(settings), handler).url == "https://telegra.ph/hello-01-01"


def test_bluesky_facet_uses_utf8_byte_offsets():
    facets = build_link_facets(MSG, LINK)
    start, end = facets[0]["index"]["byteStart"], facets[0]["index"]["byteEnd"]
    assert MSG.encode("utf-8")[start:end].decode() == LINK
    assert start > MSG.index(LINK)  # 'é'/'ö' are 2 bytes, so byte offset > char offset


def test_bluesky_flow():
    captured = {}

    def handler(request):
        if request.url.path.endswith("createSession"):
            return httpx.Response(
                200, json={"accessJwt": "jwt", "did": "did:plc:abc", "handle": "me.bsky.social"}
            )
        captured["auth"] = request.headers["authorization"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"uri": "at://did:plc:abc/app.bsky.feed.post/3kxyz", "cid": "c"})

    post = run(Bluesky(cfg(bluesky_identifier="me", bluesky_app_password="pw")), handler)
    assert post.url == "https://bsky.app/profile/me.bsky.social/post/3kxyz"
    assert post.meta["at_uri"].endswith("3kxyz")
    assert captured["auth"] == "Bearer jwt"
    assert captured["body"]["record"]["facets"][0]["features"][0]["uri"] == LINK


def test_bluesky_bad_login():
    handler = lambda r: httpx.Response(401, json={"error": "AuthenticationRequired", "message": "Invalid identifier or password"})
    with pytest.raises(PlatformError, match="Invalid identifier or password"):
        run(Bluesky(cfg(bluesky_identifier="me", bluesky_app_password="bad")), handler)


def test_gist_is_public():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json={"html_url": "https://gist.github.com/me/abc"})

    post = run(GitHubGist(cfg(github_token="gh")), handler)
    assert post.url == "https://gist.github.com/me/abc"
    assert seen["body"]["public"] is True


def test_telegram_url_and_error_never_contains_token():
    ok = lambda r: httpx.Response(200, json={"ok": True, "result": {"message_id": 42}})
    settings = cfg(telegram_bot_token="123:SECRET", telegram_channel_username="@mychan")
    post = run(Telegram(settings), ok)
    assert post.url == "https://t.me/mychan/42" and "SECRET" not in post.url

    bad = lambda r: httpx.Response(400, json={"ok": False, "description": "Bad Request: chat not found"})
    with pytest.raises(PlatformError) as exc:
        run(Telegram(settings), bad)
    assert "chat not found" in str(exc.value) and "SECRET" not in str(exc.value)


def test_missing_credentials_are_named():
    assert DevTo(cfg(devto_api_key="   ")).missing_credentials() == ["DEVTO_API_KEY"]


