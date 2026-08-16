from __future__ import annotations

from requests import HTTPError

from core.exceptions import NetworkError, ValidationError
from core.message_sanitizer import extract_backend_message
from services.api import FAST_TIMEOUT
from services.base_service import BaseApiService


class TransferService(BaseApiService):
    def validate_recipient(self, identifier: str) -> dict:
        try:
            data = self.get_json(f"/users/search/{identifier}", timeout=FAST_TIMEOUT)
        except HTTPError as exc:
            message = extract_backend_message(
                getattr(exc.response, "data", None),
                fallback="Recipient not found.",
            )
            raise ValidationError(message) from exc
        if not isinstance(data, dict):
            raise NetworkError("Unexpected recipient response.")
        return data

    def send_money(self, payload: dict) -> dict:
        try:
            data = self.post_json("/wallet/transfer", payload=payload, timeout=FAST_TIMEOUT)
        except HTTPError as exc:
            message = extract_backend_message(
                getattr(exc.response, "data", None),
                fallback="Transfer failed.",
            )
            raise NetworkError(message) from exc
        return data if isinstance(data, dict) else {"status": "success", "payload": data}
