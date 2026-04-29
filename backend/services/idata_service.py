from __future__ import annotations

from typing import Any

import httpx

from backend.core.config import settings


class IDataApiError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class IDataService:
    def __init__(self) -> None:
        self.api_key = str(getattr(settings, "IDATA_API_KEY", "") or "").strip()
        self.base_url = str(getattr(settings, "IDATA_BASE_URL", "") or "").strip().rstrip("/")
        self.timeout_seconds = float(getattr(settings, "IDATA_TIMEOUT_SECONDS", 12.0) or 12.0)

    def is_configured(self) -> bool:
        return bool(self.api_key and self.base_url)

    async def place_order(self, *, network: str, beneficiary: str, bundle_package_id: int) -> dict:
        if not self.api_key:
            raise IDataApiError("IDATA_API_KEY is not configured.")
        if not self.base_url:
            raise IDataApiError("IDATA_BASE_URL is not configured.")

        url = f"{self.base_url}/place-order"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "network": str(network or "").strip(),
            "beneficiary": str(beneficiary or "").strip(),
            "pa_data-bundle-packages": int(bundle_package_id),
        }

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds)) as client:
                response = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise IDataApiError("iData request timed out.") from exc
        except httpx.HTTPError as exc:
            raise IDataApiError("Unable to reach iData provider.") from exc

        try:
            data = response.json()
        except ValueError:
            data = {"raw": response.text}

        if response.status_code >= 400:
            message = f"iData request failed with status {response.status_code}."
            if isinstance(data, dict):
                maybe = data.get("message") or data.get("detail") or data.get("error")
                if isinstance(maybe, str) and maybe.strip():
                    message = maybe.strip()
            raise IDataApiError(message, status_code=response.status_code, response=data)

        if not isinstance(data, dict):
            raise IDataApiError("Unexpected iData response format.", status_code=response.status_code, response=data)

        return data
