from __future__ import annotations

from api.client import FAST_TIMEOUT, api_client
from core.exceptions import PaymentError


class DepositService:
    def create_deposit(self, amount: float, method: str) -> dict:
        result = api_client.request(
            "POST",
            "/payments/deposit",
            payload={"amount": float(amount), "method": method},
            timeout=FAST_TIMEOUT,
        )
        status_code = int(result.get("status_code", 0) or 0)
        data = result.get("data", {})
        if status_code >= 400:
            message = ""
            if isinstance(data, dict):
                message = str(data.get("detail") or data.get("message") or "").strip()
            raise PaymentError(message or "Unable to create deposit request.")
        return data if isinstance(data, dict) else {"status": "pending", "payload": data}

    def verify_payment(self, reference: str) -> dict:
        result = api_client.request(
            "POST",
            "/payments/verify",
            payload={"reference": str(reference or "").strip()},
            timeout=FAST_TIMEOUT,
        )
        status_code = int(result.get("status_code", 0) or 0)
        data = result.get("data", {})
        if status_code >= 400:
            message = ""
            if isinstance(data, dict):
                message = str(data.get("detail") or data.get("message") or "").strip()
            raise PaymentError(message or "Unable to verify payment.")
        return data if isinstance(data, dict) else {"status": "verified", "payload": data}
