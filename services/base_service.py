from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from services.api import DEFAULT_TIMEOUT, api


class BaseApiService:
    default_timeout = DEFAULT_TIMEOUT

    @staticmethod
    def extract_items(
        payload: Any,
        keys: Iterable[str] = ("items", "results", "transactions", "notifications", "data"),
    ) -> list[dict]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in keys:
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

    @staticmethod
    def extract_mapping(payload: Any) -> dict:
        return payload if isinstance(payload, dict) else {}

    def request_json(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        params: dict | None = None,
        headers: dict | None = None,
        timeout=None,
        failover: bool = True,
    ) -> Any:
        response = api.request(
            method,
            path,
            payload=payload,
            params=params,
            headers=headers,
            timeout=timeout or self.default_timeout,
            failover=failover,
        )
        response.raise_for_status()
        return response.json()

    def get_json(
        self,
        path: str,
        params: dict | None = None,
        headers: dict | None = None,
        timeout=None,
        failover: bool = True,
    ) -> Any:
        return self.request_json(
            "GET",
            path,
            params=params,
            headers=headers,
            timeout=timeout,
            failover=failover,
        )

    def post_json(
        self,
        path: str,
        payload: dict | None = None,
        headers: dict | None = None,
        timeout=None,
        failover: bool = True,
    ) -> Any:
        return self.request_json(
            "POST",
            path,
            payload=payload,
            headers=headers,
            timeout=timeout,
            failover=failover,
        )
