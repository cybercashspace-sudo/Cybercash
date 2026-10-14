from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

def _normalize_auth_header(raw_value: str | None) -> str:
    auth = str(raw_value or "").strip()
    if not auth:
        return ""
    return auth if auth.lower().startswith("basic ") else f"Basic {auth}"


class HubtelOTPClient:
    def __init__(self) -> None:
        self.base_url = str(os.getenv("HUBTEL_BASE_URL", "https://api-otp.hubtel.com") or "").strip().rstrip("/")
        self.auth = _normalize_auth_header(os.getenv("HUBTEL_AUTH"))
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
