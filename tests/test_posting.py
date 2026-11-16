"""API-level tests using fake platforms (no network)."""
import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app, get_service
from app.platforms.base import BasePlatform, PlatformError, PublishedPost
from app.services.posting_service import PostingService

MSG = "Grow your online visibility. https://example.com"


class Fake(BasePlatform):
    name = "Fake"
    creds = {"FAKE_TOKEN": "x"}

    def credentials(self):
        return self.creds

    async def publish(self, client, message, link):
        return PublishedPost(url="https://fake.test/1", public_access=True)


class Boom(Fake):
    name = "Boom"

    async def publish(self, client, message, link):
        raise RuntimeError("kaboom with secret-token-123")


class Rejected(Fake):
    name = "Rejected"

    async def publish(self, client, message, link):
        raise PlatformError("Authentication failed (HTTP 401)")


class Unconfigured(Fake):
    name = "Unconfigured"
    creds = {"FAKE_TOKEN": None, "OTHER": ""}


class Slow(Fake):
    name = "Slow"

    async def publish(self, client, message, link):
        await asyncio.sleep(5)


class NetDown(Fake):
    name = "NetDown"

    async def publish(self, client, message, link):
        raise httpx.ConnectError("https://api.telegram.org/botSECRET/sendMessage")


def make_client(platforms, timeout=0.2):
    service = PostingService(
        [p(Settings(_env_file=None)) for p in platforms],
        client=httpx.AsyncClient(),
        platform_timeout=timeout,
    )
    app.dependency_overrides[get_service] = lambda: service
    return TestClient(app)


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    app.dependency_overrides.clear()


def test_one_failure_does_not_stop_others():
    client = make_client([Fake, Boom, Rejected, Unconfigured, Slow, NetDown])
    body = client.post("/posting", json={"message": MSG}).json()

    by_name = {r["platform"]: r for r in body["results"]}
    assert body["success"] is True
    assert body["summary"] == {"total": 6, "succeeded": 1, "failed": 5}

    ok = by_name["Fake"]
    assert ok["status"] == "success" and ok["public_access"] is True
    assert ok["posted_url"] == "https://fake.test/1" and ok["error"] is None
    assert len(ok["date"]) == 10 and len(ok["time"]) == 8

    assert by_name["Rejected"]["error"] == "Authentication failed (HTTP 401)"
    assert by_name["Unconfigured"]["error"] == "Missing credentials: FAKE_TOKEN, OTHER"
    assert "Timed out" in by_name["Slow"]["error"]
    assert by_name["Boom"]["error"] == "Unexpected error: RuntimeError"
    for name in ("Boom", "NetDown", "Slow", "Rejected", "Unconfigured"):
        r = by_name[name]
        assert r["status"] == "failed" and r["posted_url"] is None
        assert r["public_access"] is False and r["date"] is None and r["time"] is None


def test_errors_never_leak_secrets():
    client = make_client([Boom, NetDown])
    text = client.post("/posting", json={"message": MSG}).text
    assert "secret-token-123" not in text and "SECRET" not in text


def test_all_failed_reports_success_false():
    client = make_client([Unconfigured, Rejected])
    body = client.post("/posting", json={"message": MSG}).json()
    assert body["success"] is False and body["summary"]["succeeded"] == 0


@pytest.mark.parametrize(
    "payload, expected",
    [
        ({"message": "no link"}, "found none"),
        ({"message": "a https://a.com b https://b.com"}, "found 2"),
        ({"message": "x" * 201}, "200 characters"),
        ({}, "Field required"),
        ({"message": 123}, "valid string"),
    ],
)
def test_validation_errors_are_422_and_clear(payload, expected):
    client = make_client([Fake])
    response = client.post("/posting", json=payload)
    body = response.json()
    assert response.status_code == 422
    assert body["success"] is False and body["error"] == "validation_error"
    assert body["details"][0]["field"] == "message"
    assert expected in body["details"][0]["message"]


def test_verified_public_access_uses_check_public():
    class Verified(Fake):
        name = "Verified"

        async def publish(self, client, message, link):
            return PublishedPost(url="https://fake.test/p")  # public_access=None

    async def handler(request):
        return httpx.Response(200 if request.url.path == "/p" else 404)

    service = PostingService(
        [Verified(Settings(_env_file=None))],
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    results = asyncio.run(service.publish_all(MSG))
    assert results[0].status == "success" and results[0].public_access is True


def test_health_and_platform_listing():
    client = make_client([Fake, Unconfigured])
    assert client.get("/health").json() == {"status": "ok"}
    listing = client.get("/platforms").json()
    assert listing[0] == {"platform": "Fake", "configured": True, "missing_credentials": []}
    assert listing[1]["configured"] is False
