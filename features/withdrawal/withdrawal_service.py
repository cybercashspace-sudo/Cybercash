from __future__ import annotations

from requests import HTTPError

from core.exceptions import NetworkError
from core.message_sanitizer import extract_backend_message
from services.api import FAST_TIMEOUT
from services.base_service import BaseApiService


class WithdrawalService(BaseApiService):
    def create_withdrawal(self, payload: dict) -> dict:
        try:
            data = self.post_json("/wallet/withdraw", payload=payload, timeout=FAST_TIMEOUT)
        except HTTPError as exc:
            message = extract_backend_message(
                getattr(exc.response, "data", None),
                fallback="Withdrawal request failed.",
            )
            raise NetworkError(message) from exc
        return data if isinstance(data, dict) else {"status": "pending", "payload": data}

    def check_status(self, withdrawal_id: str) -> dict:
        try:
            data = self.get_json(f"/withdrawals/{withdrawal_id}", timeout=FAST_TIMEOUT)
        except HTTPError as exc:
            message = extract_backend_message(
                getattr(exc.response, "data", None),
                fallback="Unable to fetch withdrawal status.",
            )
            raise NetworkError(message) from exc
        return data if isinstance(data, dict) else {"status": "pending", "payload": data}
