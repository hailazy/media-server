"""Async HTTP client for SillyTavern's internal REST API.

ST gates all `/api/*` POSTs behind CSRF — fetch a token from `/csrf-token` and replay it
in `X-CSRF-Token` on every subsequent POST. The session cookie issued alongside the token
binds the token, so we keep both in a single AsyncClient instance with cookie persistence.
"""

import os
from typing import Any

import httpx

ST_URL = os.getenv("ST_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = float(os.getenv("ST_TIMEOUT", "30.0"))


class STError(Exception):
    """ST API call failed."""


class STClient:
    """Singleton HTTP client with CSRF token + session cookie persistence."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._csrf: str | None = None

    async def _ensure(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=TIMEOUT, base_url=ST_URL)
        if self._csrf is None:
            await self._refresh_csrf()
        return self._client

    async def _refresh_csrf(self) -> None:
        assert self._client is not None
        r = await self._client.get("/csrf-token")
        r.raise_for_status()
        self._csrf = r.json()["token"]

    async def post(self, path: str, body: dict | None = None) -> Any:
        client = await self._ensure()
        payload = body or {}
        try:
            r = await client.post(
                path,
                json=payload,
                headers={"X-CSRF-Token": self._csrf or ""},
            )
            # CSRF token can rotate; refresh + retry once on 403
            if r.status_code == 403:
                await self._refresh_csrf()
                r = await client.post(
                    path,
                    json=payload,
                    headers={"X-CSRF-Token": self._csrf or ""},
                )
            r.raise_for_status()
            ct = r.headers.get("content-type", "")
            if "application/json" in ct:
                return r.json()
            return r.text
        except httpx.ConnectError as e:
            raise STError(
                f"Cannot reach SillyTavern at {ST_URL}. "
                "Is the container running? Try: ./scripts/up.sh sillytavern"
            ) from e
        except httpx.HTTPStatusError as e:
            raise STError(
                f"ST API {path} returned {e.response.status_code}: "
                f"{e.response.text[:200]}"
            ) from e


_client = STClient()


async def st_post(path: str, body: dict | None = None) -> Any:
    """Wrapper for the singleton client; preserves earlier import surface."""
    return await _client.post(path, body)
