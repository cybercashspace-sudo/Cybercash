from __future__ import annotations

from api.client import FAST_TIMEOUT, api_client
from core.exceptions import NetworkError, ValidationError


class TransferService:
    def validate_recipient(self, identifier: str) -> dict:
        result = api_client.request("GET", f"/users/search/{identifier}", timeout=FAST_TIMEOUT)
        status_code = int(result.get("status_code", 0) or 0)
        data = result.get("data", {})
        if status_code >= 400:
            message = ""
            if isinstance(data, dict):
                message = str(data.get("detail") or data.get("message") or "").strip()
            raise ValidationError(message or "Recipient not found.")
        if not isinstance(data, dict):
            raise NetworkError("Unexpected recipient response.")
        return data

    def send_money(self, payload: dict) -> dict:
        result = api_client.request("POST", "/wallet/transfer", payload=payload, timeout=FAST_TIMEOUT)
        status_code = int(result.get("status_code", 0) or 0)
        data = result.get("data", {})
        if status_code >= 400:
            message = ""
            if isinstance(data, dict):
                message = str(data.get("detail") or data.get("message") or "").strip()
            raise NetworkError(message or "Transfer failed.")
        return data if isinstance(data, dict) else {"status": "success", "payload": data}
