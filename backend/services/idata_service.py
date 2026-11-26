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
        outcome_unknown: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response = response
        self.outcome_unknown = bool(outcome_unknown)


class IDataService:
    def __init__(self) -> None:
        self.api_key = str(getattr(settings, "IDATA_API_KEY", "") or "").strip()
        self.base_url = str(getattr(settings, "IDATA_BASE_URL", "") or "").strip().rstrip("/")
        if self.base_url.lower().endswith("/place-order"):
            self.base_url = self.base_url[: -len("/place-order")]
        self.timeout_seconds = float(getattr(settings, "IDATA_TIMEOUT_SECONDS", 12.0) or 12.0)

    def is_configured(self) -> bool:
        return bool(self.api_key and self.base_url)

    @staticmethod
    def order_receipt(data: dict[str, Any]) -> dict[str, Any]:
        """Keep only fields required by the app; omit provider internals."""
        allowed = ("status", "order_status", "order_id", "amount", "network", "beneficiary")
        return {key: data[key] for key in allowed if data.get(key) not in (None, "")}

    async def place_order(self, *, network: str, beneficiary: str, bundle_package_id: int) -> dict:
        if not self.api_key:
            raise IDataApiError("IDATA_API_KEY is not configured.")
        if not self.base_url:
            raise IDataApiError("IDATA_BASE_URL is not configured.")

        # Accept either the documented API root or the complete endpoint URL.
        base_url = self.base_url.rstrip("/")
        url = base_url if base_url.lower().endswith("/place-order") else f"{base_url}/place-order"
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
        except httpx.ConnectTimeout as exc:
            raise IDataApiError("The data provider is temporarily unavailable. Please try again shortly.") from exc
        except httpx.TimeoutException as exc:
            raise IDataApiError(
                "The provider is still confirming this order. Check its status before retrying.",
                outcome_unknown=True,
            ) from exc
        except httpx.HTTPError as exc:
            raise IDataApiError(
                "The provider is still confirming this order. Check its status before retrying.",
                outcome_unknown=True,
            ) from exc

        try:
            data = response.json()
        except ValueError:
            data = None

        if response.status_code >= 400:
            raise IDataApiError(
                "The data provider could not accept this order. No bundle was purchased."
                if response.status_code < 500
                else "The provider is still confirming this order. Check its status before retrying.",
                status_code=response.status_code,
                outcome_unknown=response.status_code >= 500,
            )

        if not isinstance(data, dict):
            raise IDataApiError(
                "The data provider returned an unreadable response. Check order status before retrying.",
                status_code=response.status_code,
                outcome_unknown=True,
            )

        return data

    async def _get(self, endpoint: str, *, params: dict[str, Any] | None = None) -> Any:
        if not self.api_key:
            raise IDataApiError("IDATA_API_KEY is not configured.")
        if not self.base_url:
            raise IDataApiError("IDATA_BASE_URL is not configured.")

        url = f"{self.base_url}/{endpoint.strip('/')}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds)) as client:
                response = await client.get(url, params=params or {}, headers=headers)
        except httpx.TimeoutException as exc:
            raise IDataApiError("The data provider is taking longer than expected. Please try again shortly.") from exc
        except httpx.HTTPError as exc:
            raise IDataApiError("The data provider is temporarily unavailable. Please try again shortly.") from exc

        try:
            data = response.json()
        except ValueError:
            data = None

        if response.status_code >= 400:
            raise IDataApiError(
                "Live data bundle information is temporarily unavailable. Please refresh shortly.",
                status_code=response.status_code,
            )

        return data

    async def fetch_packages(self, *, network: str) -> list[dict[str, Any]]:
        data = await self._get("packages", params={"network": str(network or "").strip().lower()})
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            for key in ("packages", "data", "results", "items"):
                value = data.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        raise IDataApiError("Unexpected iData packages response format.", response=data)

    async def wallet_balance(self) -> dict[str, Any]:
        data = await self._get("wallet-balance")
        if not isinstance(data, dict):
            raise IDataApiError("Unexpected iData wallet response format.", response=data)
        return data

    async def order_status(self, *, order_id: int | str) -> dict[str, Any]:
        data = await self._get("order-status", params={"order_id": str(order_id).strip()})
        if not isinstance(data, dict):
            raise IDataApiError("Unexpected iData order status response format.", response=data)
        return data
