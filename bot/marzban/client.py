import time

import httpx


class MarzbanAuthError(Exception):
    pass


class MarzbanClient:
    def __init__(self, base_url: str, username: str, password: str, transport: httpx.BaseTransport | None = None):
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._transport = transport
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=self._transport, timeout=10)

    async def _get_token(self) -> str:
        if self._token and time.monotonic() < self._token_expires_at:
            return self._token
        async with self._client() as client:
            response = await client.post(
                f"{self._base_url}/api/admin/token",
                data={"username": self._username, "password": self._password},
            )
        if response.status_code != 200:
            raise MarzbanAuthError(f"Marzban auth failed: {response.status_code}")
        data = response.json()
        self._token = data["access_token"]
        self._token_expires_at = time.monotonic() + 3000
        return self._token

    async def get_user(self, login: str) -> dict | None:
        token = await self._get_token()
        async with self._client() as client:
            response = await client.get(
                f"{self._base_url}/api/user/{login}",
                headers={"Authorization": f"Bearer {token}"},
            )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
