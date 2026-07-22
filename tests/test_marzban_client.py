import httpx
import pytest

from bot.marzban.client import MarzbanAuthError, MarzbanClient


def _handler_factory(user_payload: dict | None, status_code: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/admin/token":
            return httpx.Response(200, json={"access_token": "test-token", "token_type": "bearer"})
        if request.url.path == "/api/user/ivan":
            if user_payload is None:
                return httpx.Response(404, json={"detail": "Not found"})
            return httpx.Response(status_code, json=user_payload)
        return httpx.Response(404)

    return handler


async def test_get_user_returns_data():
    transport = httpx.MockTransport(
        _handler_factory({"username": "ivan", "status": "active", "used_traffic": 123, "data_limit": 1000, "expire": 1999999999})
    )
    client = MarzbanClient("https://panel.example.com", "admin", "pass", transport=transport)

    data = await client.get_user("ivan")

    assert data["username"] == "ivan"
    assert data["status"] == "active"


async def test_get_user_returns_none_for_missing_user():
    transport = httpx.MockTransport(_handler_factory(None))
    client = MarzbanClient("https://panel.example.com", "admin", "pass", transport=transport)

    data = await client.get_user("ivan")

    assert data is None


async def test_auth_failure_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "unauthorized"})

    transport = httpx.MockTransport(handler)
    client = MarzbanClient("https://panel.example.com", "admin", "wrong", transport=transport)

    with pytest.raises(MarzbanAuthError):
        await client.get_user("ivan")
