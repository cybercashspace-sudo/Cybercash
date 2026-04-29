from __future__ import annotations

import logging
import os
from typing import Any

import requests

from utils.network import normalize_ghana_number


logger = logging.getLogger(__name__)


def _format_ghana_e164(phone_number: str) -> str:
    normalized = normalize_ghana_number(phone_number)
    digits = "".join(ch for ch in normalized if ch.isdigit())
    if not digits:
        return ""

    if digits.startswith("233") and len(digits) == 12:
        return f"+{digits}"
    if digits.startswith("0") and len(digits) == 10:
        return f"+233{digits[1:]}"
    if len(digits) == 9:
        return f"+233{digits}"
    if normalized.startswith("+"):
        return normalized
    return f"+{digits}"


def _normalize_auth_header(raw_value: str | None) -> str:
    auth = str(raw_value or "").strip()
    if not auth:
        return ""
    return auth if auth.lower().startswith("basic ") else f"Basic {auth}"


class HubtelOTPClient:
    def __init__(self) -> None:
        self.base_url = str(os.getenv("HUBTEL_BASE_URL", "https://api-otp.hubtel.com") or "").strip().rstrip("/")
        self.auth = _normalize_auth_header(os.getenv("HUBTEL_AUTH"))
        self.sender_id = str(os.getenv("HUBTEL_SENDER_ID", "CyberCash") or "CyberCash").strip() or "CyberCash"
        self.country_code = str(os.getenv("HUBTEL_COUNTRY_CODE", "GH") or "GH").strip().upper() or "GH"
        self.timeout_seconds = float(os.getenv("HUBTEL_TIMEOUT_SECONDS", "10") or 10)

    def _headers(self) -> dict[str, str]:
        if not self.auth:
            return {}
        return {
            "Authorization": self.auth,
            "Content-Type": "application/json",
        }

    @staticmethod
    def _safe_json(response: Any) -> dict[str, Any]:
        try:
            payload = response.json()
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _missing_config_error(self) -> dict:
        return {
            "status": "error",
            "provider": "hubtel",
            "detail": "HUBTEL_AUTH is not configured.",
        }

    def _invalid_sender_error(self) -> dict:
        return {
            "status": "error",
            "provider": "hubtel",
            "detail": "HUBTEL_SENDER_ID must be 11 characters or fewer.",
        }

    def send_otp(self, phone_number: str) -> dict:
        if not self.auth:
            return self._missing_config_error()
        if len(self.sender_id) > 11:
            return self._invalid_sender_error()

        recipient = _format_ghana_e164(phone_number)
        if not recipient:
            return {
                "status": "error",
                "provider": "hubtel",
                "detail": "Invalid phone number.",
            }

        url = f"{self.base_url}/otp/send"
        payload = {
            "senderId": self.sender_id,
            "phoneNumber": recipient,
            "countryCode": self.country_code,
        }

        try:
            response = requests.post(url, json=payload, headers=self._headers(), timeout=self.timeout_seconds)
            response_payload = self._safe_json(response)
            response_code = str(response_payload.get("code") or response_payload.get("Code") or "").strip()
            response_data = response_payload.get("data") if isinstance(response_payload.get("data"), dict) else {}

            if not getattr(response, "ok", False) or (response_code and response_code != "0000"):
                detail = (
                    str(response_payload.get("message") or response_payload.get("Message") or "").strip()
                    or (str(getattr(response, "text", "") or "")[:300])
                    or "Hubtel OTP request failed."
                )
                return {
                    "status": "error",
                    "provider": "hubtel",
                    "detail": detail,
                    "code": response_code or None,
                    "http_status": getattr(response, "status_code", None),
                }

            request_id = str(response_data.get("requestId") or response_payload.get("requestId") or "").strip()
            prefix = str(response_data.get("prefix") or response_payload.get("prefix") or "").strip()
            if not request_id or not prefix:
                return {
                    "status": "error",
                    "provider": "hubtel",
                    "detail": "Hubtel OTP response missing requestId or prefix.",
                    "http_status": getattr(response, "status_code", None),
                }

            return {
                "status": "queued",
                "provider": "hubtel",
                "message": str(response_payload.get("message") or "success"),
                "request_id": request_id,
                "prefix": prefix,
                "http_status": getattr(response, "status_code", None),
            }
        except Exception as exc:
            logger.warning("Hubtel OTP send failed: %s", exc)
            return {
                "status": "error",
                "provider": "hubtel",
                "detail": str(exc),
            }

    def resend_otp(self, request_id: str) -> dict:
        if not self.auth:
            return self._missing_config_error()

        request_id = str(request_id or "").strip()
        if not request_id:
            return {
                "status": "error",
                "provider": "hubtel",
                "detail": "requestId is required.",
            }

        url = f"{self.base_url}/otp/resend"
        payload = {"requestId": request_id}

        try:
            response = requests.post(url, json=payload, headers=self._headers(), timeout=self.timeout_seconds)
            response_payload = self._safe_json(response)
            response_code = str(response_payload.get("code") or response_payload.get("Code") or "").strip()
            response_data = response_payload.get("data") if isinstance(response_payload.get("data"), dict) else {}

            if not getattr(response, "ok", False) or (response_code and response_code != "0000"):
                detail = (
                    str(response_payload.get("message") or response_payload.get("Message") or "").strip()
                    or (str(getattr(response, "text", "") or "")[:300])
                    or "Hubtel OTP resend failed."
                )
                return {
                    "status": "error",
                    "provider": "hubtel",
                    "detail": detail,
                    "code": response_code or None,
                    "http_status": getattr(response, "status_code", None),
                }

            refreshed_request_id = str(response_data.get("requestId") or response_payload.get("requestId") or request_id).strip()
            prefix = str(response_data.get("prefix") or response_payload.get("prefix") or "").strip()
            return {
                "status": "queued",
                "provider": "hubtel",
                "message": str(response_payload.get("message") or "success"),
                "request_id": refreshed_request_id or request_id,
                "prefix": prefix,
                "http_status": getattr(response, "status_code", None),
            }
        except Exception as exc:
            logger.warning("Hubtel OTP resend failed: %s", exc)
            return {
                "status": "error",
                "provider": "hubtel",
                "detail": str(exc),
            }

    def verify_otp(self, request_id: str, prefix: str, code: str) -> dict:
        if not self.auth:
            return self._missing_config_error()

        request_id = str(request_id or "").strip()
        prefix = str(prefix or "").strip()
        code = str(code or "").strip()
        if not request_id or not prefix or not code:
            return {
                "status": "error",
                "provider": "hubtel",
                "detail": "requestId, prefix and code are required.",
            }

        url = f"{self.base_url}/otp/verify"
        payload = {
            "requestId": request_id,
            "prefix": prefix,
            "code": code,
        }

        try:
            response = requests.post(url, json=payload, headers=self._headers(), timeout=self.timeout_seconds)
            if getattr(response, "ok", False):
                return {
                    "status": "verified",
                    "provider": "hubtel",
                    "http_status": getattr(response, "status_code", None),
                }

            response_payload = self._safe_json(response)
            detail = (
                str(response_payload.get("message") or response_payload.get("Message") or "").strip()
                or (str(getattr(response, "text", "") or "")[:300])
                or "Hubtel OTP verification failed."
            )
            return {
                "status": "error",
                "provider": "hubtel",
                "detail": detail,
                "http_status": getattr(response, "status_code", None),
            }
        except Exception as exc:
            logger.warning("Hubtel OTP verify failed: %s", exc)
            return {
                "status": "error",
                "provider": "hubtel",
                "detail": str(exc),
            }
