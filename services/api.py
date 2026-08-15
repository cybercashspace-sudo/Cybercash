from __future__ import annotations

import json
from typing import Any

import requests

from api.client import APIClient, API_URL, DEFAULT_TIMEOUT, FAST_TIMEOUT, api_client


def _extract_message(payload: object, status_code: int) -> str:
    if isinstance(payload, dict):
        for key in ("detail", "message", "error", "description"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if isinstance(payload, str) and payload.strip():
        return payload.strip()
    return f"HTTP {status_code}"


class ResponseAdapter:
    """Minimal requests.Response-compatible wrapper for the shared API client."""

    def __init__(self, status_code: int, data: Any, *, url: str = "", headers: dict | None = None):
        self.status_code = int(status_code or 0)
        self.data = data
        self.ok = self.status_code < 400
        self.url = url
        self.headers = dict(headers or {})
        self.reason = ""
        self.content = self._build_content(data)
        self.text = self.content.decode("utf-8", errors="ignore")

    @staticmethod
    def _build_content(data: Any) -> bytes:
        if data is None:
            return b""
        if isinstance(data, bytes):
            return data
        if isinstance(data, (dict, list)):
            try:
                return json.dumps(data, ensure_ascii=False).encode("utf-8")
            except Exception:
                return str(data).encode("utf-8")
        return str(data).encode("utf-8")

    def json(self):
        return self.data if self.data is not None else {}

    def raise_for_status(self):
        if self.ok:
            return None
        raise requests.HTTPError(_extract_message(self.data, self.status_code), response=self)


class CompatAPI:
    """Response-style facade over the normalized API client."""

    def __init__(self, client: APIClient | None = None):
        self._client = client or api_client

    def request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        params: dict | None = None,
        headers: dict | None = None,
        timeout=DEFAULT_TIMEOUT,
        failover: bool = True,
    ) -> ResponseAdapter:
        result = self._client.request(
            method=method,
            path=path,
            payload=payload,
            params=params,
            headers=headers,
            timeout=timeout,
            failover=failover,
        )
        return ResponseAdapter(
            status_code=int(result.get("status_code", 0) or 0),
            data=result.get("data"),
            url=str(result.get("url", "") or ""),
            headers=headers,
        )

    def get(
        self,
        path: str,
        params: dict | None = None,
        headers: dict | None = None,
        timeout=DEFAULT_TIMEOUT,
        failover: bool = True,
    ) -> ResponseAdapter:
        return self.request(
            "GET",
            path,
            params=params,
            headers=headers,
            timeout=timeout,
            failover=failover,
        )

    def post(
        self,
        path: str,
        payload: dict | None = None,
        headers: dict | None = None,
        timeout=DEFAULT_TIMEOUT,
        failover: bool = True,
    ) -> ResponseAdapter:
        return self.request(
            "POST",
            path,
            payload=payload,
            headers=headers,
            timeout=timeout,
            failover=failover,
        )

    def put(
        self,
        path: str,
        payload: dict | None = None,
        headers: dict | None = None,
        timeout=DEFAULT_TIMEOUT,
        failover: bool = True,
    ) -> ResponseAdapter:
        return self.request(
            "PUT",
            path,
            payload=payload,
            headers=headers,
            timeout=timeout,
            failover=failover,
        )

    def patch(
        self,
        path: str,
        payload: dict | None = None,
        headers: dict | None = None,
        timeout=DEFAULT_TIMEOUT,
        failover: bool = True,
    ) -> ResponseAdapter:
        return self.request(
            "PATCH",
            path,
            payload=payload,
            headers=headers,
            timeout=timeout,
            failover=failover,
        )

    def warmup(self) -> None:
        self._client.warmup()

    @property
    def client(self) -> APIClient:
        return self._client


api = CompatAPI()

__all__ = [
    "APIClient",
    "API_URL",
    "DEFAULT_TIMEOUT",
    "FAST_TIMEOUT",
    "ResponseAdapter",
    "CompatAPI",
    "api",
    "api_client",
]
