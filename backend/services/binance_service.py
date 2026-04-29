from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from backend.core.config import settings


@dataclass(frozen=True)
class BinanceCredentials:
    api_key: str
    secret_key: str


class BinanceApiError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: int | None = None,
        response: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.response = response


class BinanceService:
    """
    Minimal Binance Spot API wrapper using direct signed HTTP requests.
    Keeps all secrets server-side (env only) and never logs keys.
    """

    def __init__(self) -> None:
        def _normalize_secret(value: str) -> str:
            cleaned = str(value or "").strip()
            if not cleaned:
                return ""
            if cleaned.upper().startswith("YOUR_"):
                return ""
            return cleaned

        api_key = _normalize_secret(getattr(settings, "BINANCE_API_KEY", ""))
        secret_key = _normalize_secret(getattr(settings, "BINANCE_SECRET_KEY", "")) or _normalize_secret(
            getattr(settings, "BINANCE_API_SECRET", "")
        )
        self.credentials = BinanceCredentials(api_key=api_key, secret_key=secret_key)
        self.base_url = str(getattr(settings, "BINANCE_BASE_URL", "https://api.binance.com") or "").strip().rstrip("/")
        self.timeout_seconds = float(getattr(settings, "BINANCE_TIMEOUT_SECONDS", 10.0) or 10.0)
        self.recv_window = int(getattr(settings, "BINANCE_RECV_WINDOW", 5000) or 5000)

        self._time_offset_ms = 0

    def is_configured(self) -> bool:
        return bool(self.credentials.api_key and self.credentials.secret_key and self.base_url)

    def _timestamp_ms(self) -> int:
        return int(time.time() * 1000) + int(self._time_offset_ms)

    def _sign(self, query: str) -> str:
        return hmac.new(
            self.credentials.secret_key.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    async def _sync_time(self) -> None:
        url = f"{self.base_url}/api/v3/time"
        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds)) as client:
            response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        server_time = int(data.get("serverTime") or 0)
        if server_time <= 0:
            return
        local = int(time.time() * 1000)
        self._time_offset_ms = server_time - local

    async def _request(
        self,
        method: str,
        path: str,
        *,
        signed: bool = False,
        params: dict[str, Any] | None = None,
        _retry_after_time_sync: bool = True,
    ) -> Any:
        if not self.base_url:
            raise BinanceApiError("BINANCE_BASE_URL is not configured.")
        if signed and not self.is_configured():
            raise BinanceApiError("Binance credentials are not configured.")

        url = f"{self.base_url}{path}"
        base_params = dict(params or {})

        headers: dict[str, str] = {}
        query = ""
        if signed:
            headers["X-MBX-APIKEY"] = self.credentials.api_key

            signed_params = dict(base_params)
            signed_params.setdefault("recvWindow", self.recv_window)
            signed_params["timestamp"] = self._timestamp_ms()

            unsigned_query = urlencode(signed_params, doseq=True)
            signature = self._sign(unsigned_query)
            query = f"{unsigned_query}&signature={signature}"
        else:
            query = urlencode(base_params, doseq=True) if base_params else ""

        request_url = f"{url}?{query}" if query else url

        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds)) as client:
            response = await client.request(method.upper(), request_url, headers=headers)

        raw_text = response.text
        try:
            payload = response.json()
        except ValueError:
            payload = {"raw": raw_text}

        if response.status_code >= 400:
            message = f"Binance API request failed with status {response.status_code}."
            code = None
            if isinstance(payload, dict):
                code = payload.get("code")
                msg = payload.get("msg") or payload.get("message")
                if isinstance(msg, str) and msg.strip():
                    message = msg.strip()

            # Timestamp drift -> sync time once and retry.
            if signed and _retry_after_time_sync and isinstance(payload, dict) and payload.get("code") in {-1021}:
                await self._sync_time()
                return await self._request(
                    method,
                    path,
                    signed=signed,
                    params=base_params,
                    _retry_after_time_sync=False,
                )

            raise BinanceApiError(message, status_code=response.status_code, code=code, response=payload)

        return payload

    async def get_symbol_price(self, symbol: str) -> float:
        data = await self._request("GET", "/api/v3/ticker/price", signed=False, params={"symbol": symbol})
        if not isinstance(data, dict) or "price" not in data:
            raise BinanceApiError("Unexpected Binance price response.", response=data)
        return float(data["price"])

    async def get_account(self) -> dict:
        data = await self._request("GET", "/api/v3/account", signed=True, params={})
        if not isinstance(data, dict):
            raise BinanceApiError("Unexpected Binance account response.", response=data)
        return data

    async def get_asset_balance(self, asset: str) -> dict:
        account = await self.get_account()
        balances = account.get("balances")
        if not isinstance(balances, list):
            raise BinanceApiError("Unexpected Binance balances response.", response=account)
        asset_key = str(asset or "").strip().upper()
        for item in balances:
            if not isinstance(item, dict):
                continue
            if str(item.get("asset") or "").strip().upper() == asset_key:
                return item
        return {"asset": asset_key, "free": "0", "locked": "0"}

    async def get_deposit_address(self, *, coin: str, network: str | None = None) -> dict:
        params: dict[str, Any] = {"coin": str(coin or "").strip().upper()}
        if network:
            params["network"] = str(network).strip()
        data = await self._request("GET", "/sapi/v1/capital/deposit/address", signed=True, params=params)
        if not isinstance(data, dict):
            raise BinanceApiError("Unexpected Binance deposit address response.", response=data)
        return data

    async def get_deposit_history(
        self,
        *,
        coin: str | None = None,
        status: int | None = None,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        params: dict[str, Any] = {}
        if coin:
            params["coin"] = str(coin).strip().upper()
        if status is not None:
            params["status"] = int(status)
        if start_time_ms is not None:
            params["startTime"] = int(start_time_ms)
        if end_time_ms is not None:
            params["endTime"] = int(end_time_ms)
        if limit is not None:
            params["limit"] = int(limit)

        data = await self._request("GET", "/sapi/v1/capital/deposit/hisrec", signed=True, params=params)
        if not isinstance(data, list):
            raise BinanceApiError("Unexpected Binance deposit history response.", response=data)
        return [row for row in data if isinstance(row, dict)]

    async def withdraw(
        self,
        *,
        coin: str,
        address: str,
        amount: float,
        network: str | None = None,
        address_tag: str | None = None,
        name: str | None = None,
    ) -> dict:
        params: dict[str, Any] = {
            "coin": str(coin or "").strip().upper(),
            "address": str(address or "").strip(),
            "amount": str(float(amount)),
        }
        if network:
            params["network"] = str(network).strip()
        if address_tag:
            params["addressTag"] = str(address_tag).strip()
        if name:
            params["name"] = str(name).strip()

        data = await self._request("POST", "/sapi/v1/capital/withdraw/apply", signed=True, params=params)
        if not isinstance(data, dict):
            raise BinanceApiError("Unexpected Binance withdrawal response.", response=data)
        return data


def get_binance_service() -> BinanceService:
    return BinanceService()
