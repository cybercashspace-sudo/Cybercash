from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import dotenv_values
from fastapi import HTTPException, status

from backend.core.config import settings

PAYSTACK_AUTH_FAILURE_DETAIL = (
    "Paystack authentication failed on the backend. Restart the server so the active .env file is reloaded, "
    "then confirm the backend is reading the current Paystack secret from the correct file."
)

_BACKEND_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
_ROOT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def normalize_paystack_secret_key(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""

    if raw.upper().startswith("PAYSTACK_SECRET_KEY="):
        raw = raw.split("=", 1)[1].strip()

    raw = raw.strip().strip('"').strip("'")

    if raw.lower().startswith("bearer "):
        raw = raw[7:].strip()

    return raw.strip()


def _add_candidate_key(candidates: list[str], seen: set[str], value: Any) -> None:
    normalized = normalize_paystack_secret_key(value)
    if normalized and normalized not in seen:
        seen.add(normalized)
        candidates.append(normalized)


def get_paystack_secret_key_candidates() -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    # Prefer the live process environment first, then known config values, then
    # the two .env locations that ship with this project.
    _add_candidate_key(candidates, seen, os.getenv("PAYSTACK_SECRET_KEY"))
    _add_candidate_key(candidates, seen, getattr(settings, "PAYSTACK_SECRET_KEY", ""))
    _add_candidate_key(candidates, seen, os.getenv("PAYSTACK_SECRET"))
    _add_candidate_key(candidates, seen, os.getenv("PAYSTACK_API_SECRET_KEY"))
    _add_candidate_key(candidates, seen, os.getenv("PAYSTACK_LIVE_SECRET_KEY"))
    _add_candidate_key(candidates, seen, os.getenv("PAYSTACK_TEST_SECRET_KEY"))

    for env_path in (_ROOT_ENV_PATH, _BACKEND_ENV_PATH):
        try:
            env_values = dotenv_values(env_path)
        except Exception:
            continue

        _add_candidate_key(candidates, seen, env_values.get("PAYSTACK_SECRET_KEY"))
        _add_candidate_key(candidates, seen, env_values.get("PAYSTACK_SECRET"))
        _add_candidate_key(candidates, seen, env_values.get("PAYSTACK_API_SECRET_KEY"))
        _add_candidate_key(candidates, seen, env_values.get("PAYSTACK_LIVE_SECRET_KEY"))
        _add_candidate_key(candidates, seen, env_values.get("PAYSTACK_TEST_SECRET_KEY"))

    return candidates


def compute_paystack_signature(secret_key: str, payload: bytes) -> str:
    normalized_key = normalize_paystack_secret_key(secret_key)
    if not normalized_key:
        return ""
    return hmac.new(normalized_key.encode("utf-8"), msg=payload, digestmod=hashlib.sha512).hexdigest()


def is_valid_paystack_signature(
    signature: str,
    payload: bytes,
    secret_keys: list[str] | None = None,
) -> bool:
    expected_signature = str(signature or "").strip().lower()
    if not expected_signature:
        return False

    for secret_key in secret_keys or get_paystack_secret_key_candidates():
        computed_signature = compute_paystack_signature(secret_key, payload)
        if computed_signature and hmac.compare_digest(expected_signature, computed_signature.lower()):
            return True
    return False


class PaystackService:
    def __init__(self):
        self.base_url = "https://api.paystack.co"
        self.secret_key_candidates = get_paystack_secret_key_candidates()
        self.secret_key = self.secret_key_candidates[0] if self.secret_key_candidates else ""
        self.public_key = normalize_paystack_secret_key(getattr(settings, "PAYSTACK_PUBLIC_KEY", ""))
        self.headers = self._headers_for(self.secret_key)

    @staticmethod
    def _headers_for(secret_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {normalize_paystack_secret_key(secret_key)}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
            if isinstance(payload, dict):
                message = payload.get("message")
                if message:
                    return str(message)
        except Exception:
            pass
        return (response.text or "Unexpected Paystack error.").strip()

    async def _request_json_with_secret_fallback(
        self,
        method: str,
        path: str,
        *,
        request_kwargs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.secret_key_candidates:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Paystack secret key is not configured in the backend.",
            )

        url = f"{self.base_url}{path}"
        request_kwargs = dict(request_kwargs or {})

        async with httpx.AsyncClient(timeout=20.0) as client:
            for index, secret_key in enumerate(self.secret_key_candidates):
                headers = self._headers_for(secret_key)
                try:
                    response = await client.request(method, url, headers=headers, **request_kwargs)
                    response.raise_for_status()
                    payload = response.json()
                    if not isinstance(payload, dict):
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail="Paystack returned an unexpected response.",
                        )
                    return payload
                except httpx.HTTPStatusError as exc:
                    provider_message = self._extract_error_message(exc.response)
                    if exc.response.status_code in {401, 403}:
                        if index < len(self.secret_key_candidates) - 1:
                            continue
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=PAYSTACK_AUTH_FAILURE_DETAIL,
                        ) from exc
                    if 400 <= exc.response.status_code < 500:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Paystack rejected request: {provider_message}",
                        ) from exc
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"Paystack service unavailable: {provider_message}",
                    ) from exc
                except httpx.RequestError as exc:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"Paystack network error: {exc}",
                    ) from exc

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=PAYSTACK_AUTH_FAILURE_DETAIL,
        )

    async def initiate_payment(
        self,
        email: str,
        amount: int,
        metadata: dict = None,
        currency: str | None = None,
        callback_url: str | None = None,
    ):
        """
        Initiate a payment with Paystack.
        amount is in kobo (e.g., 10000 for GHS 100.00)
        """
        if not self.secret_key_candidates:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Paystack secret key is not configured.",
            )

        payload = {
            "email": email,
            "amount": int(amount),
            "metadata": metadata if metadata else {},
        }
        callback_value = str(callback_url or "").strip()
        if callback_value:
            payload["callback_url"] = callback_value
        currency_value = str(currency or "").strip().upper()
        if currency_value:
            payload["currency"] = currency_value

        data = await self._request_json_with_secret_fallback(
            "POST",
            "/transaction/initialize",
            request_kwargs={"json": payload},
        )
        if not data.get("status"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Paystack initiation failed: {data.get('message', 'Unknown error')}",
            )
        return data["data"]

    async def verify_payment(self, reference: str):
        """
        Verify a Paystack payment using its reference.
        """
        if not self.secret_key_candidates:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Paystack API secret key is not configured.",
            )

        data = await self._request_json_with_secret_fallback(
            "GET",
            f"/transaction/verify/{reference}",
        )
        if not data.get("status"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Paystack verification failed: {data.get('message', 'Unknown error')}",
            )
        return data["data"]


def get_paystack_service() -> PaystackService:
    return PaystackService()
