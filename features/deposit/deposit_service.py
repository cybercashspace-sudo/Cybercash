from __future__ import annotations

from requests import HTTPError

from core.exceptions import PaymentError
from core.message_sanitizer import extract_backend_message
from services.api import FAST_TIMEOUT
from services.base_service import BaseApiService


class DepositService(BaseApiService):
    def create_deposit(self, amount: float, method: str) -> dict:
        try:
            data = self.post_json(
                "/payments/deposit",
                payload={"amount": float(amount), "method": method},
                timeout=FAST_TIMEOUT,
            )
        except HTTPError as exc:
            message = extract_backend_message(
                getattr(exc.response, "data", None),
                fallback="Unable to create deposit request.",
            )
            raise PaymentError(message) from exc
        return data if isinstance(data, dict) else {"status": "pending", "payload": data}

    def verify_payment(self, reference: str) -> dict:
        try:
            data = self.post_json(
                "/payments/verify",
                payload={"reference": str(reference or "").strip()},
                timeout=FAST_TIMEOUT,
            )
        except HTTPError as exc:
            message = extract_backend_message(
                getattr(exc.response, "data", None),
                fallback="Unable to verify payment.",
            )
            raise PaymentError(message) from exc
        return data if isinstance(data, dict) else {"status": "verified", "payload": data}
