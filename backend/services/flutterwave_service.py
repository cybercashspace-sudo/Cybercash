from __future__ import annotations

import base64
import os
import time
from typing import Any, Dict, Optional, Tuple

import httpx
from fastapi import HTTPException, status

from backend.core.config import settings
from utils.network import (
    detect_flutterwave_network,
    normalize_flutterwave_momo_number,
    normalize_ghana_number,
)


class FlutterwaveService:
    def __init__(self) -> None:
        self.base_url = str(
            getattr(settings, "FLUTTERWAVE_BASE_URL", "")
            or os.getenv("FLUTTERWAVE_BASE_URL", "https://api.flutterwave.com/v3")
        ).rstrip("/")
        self.token_url = str(
            getattr(settings, "FLUTTERWAVE_TOKEN_URL", "")
            or os.getenv("FLUTTERWAVE_TOKEN_URL", "https://idp.flutterwave.com/oauth/token")
        ).strip() or "https://idp.flutterwave.com/oauth/token"
        self.client_id = str(
            getattr(settings, "FLW_CLIENT_ID", "")
            or os.getenv("FLW_CLIENT_ID", "")
        ).strip()
        self.client_secret = str(
            getattr(settings, "FLW_CLIENT_SECRET", "")
            or os.getenv("FLW_CLIENT_SECRET", "")
        ).strip()
        self.encryption_key = str(
            getattr(settings, "FLW_ENCRYPTION_KEY", "")
            or os.getenv("FLW_ENCRYPTION_KEY", "")
        ).strip()
        self.secret_key = str(
            getattr(settings, "FLUTTERWAVE_SECRET_KEY", "")
            or os.getenv("FLUTTERWAVE_SECRET_KEY", "")
        ).strip()
        self.webhook_hash = str(
            getattr(settings, "FLUTTERWAVE_WEBHOOK_HASH", "")
            or os.getenv("FLUTTERWAVE_WEBHOOK_HASH", "")
        ).strip()
        self._access_token: Optional[str] = None
        self._access_token_expires_at: float = 0.0

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
        return (response.text or "Unexpected Flutterwave error.").strip()

    @staticmethod
    def _normalize_requested_network(network: Optional[str]) -> Optional[str]:
        raw = str(network or "").strip().upper()
        if not raw:
            return None
        if raw in {"VODAFONE", "TELECEL"}:
            return "VODAFONE"
        if raw in {"AIRTEL", "AIRTELTIGO"}:
            return "AIRTELTIGO"
        if raw == "MTN":
            return "MTN"
        return raw

    def _resolve_legacy_token(self) -> str:
        if self.secret_key:
            return self.secret_key
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Flutterwave credentials are not configured.",
        )

    async def _get_oauth_token(self) -> str:
        if self._access_token and time.time() < self._access_token_expires_at:
            return self._access_token

        if not (self.client_id and self.client_secret):
            return self._resolve_legacy_token()

        credentials = f"{self.client_id}:{self.client_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        data = {"grant_type": "client_credentials"}

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(self.token_url, headers=headers, data=data)
                response.raise_for_status()
                payload = response.json()
        except HTTPException:
            raise
        except httpx.HTTPStatusError as exc:
            provider_message = self._extract_error_message(exc.response)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Flutterwave OAuth failed: {provider_message}",
            ) from exc
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Flutterwave OAuth network error: {exc}",
            ) from exc

        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Flutterwave OAuth returned an unexpected response.",
            )

        token = str(payload.get("access_token") or "").strip()
        if not token:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Flutterwave OAuth response did not include an access token.",
            )

        expires_in = int(payload.get("expires_in") or 0)
        self._access_token = token
        self._access_token_expires_at = time.time() + max(expires_in - 60, 0)
        return token

    async def _get_auth_headers(self) -> Dict[str, str]:
        token = await self._get_oauth_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def encrypt_data(self, data: str) -> str:
        if not self.encryption_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Flutterwave encryption key is not configured.",
            )

        try:
            from Crypto.Cipher import AES
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="PyCryptodome is required for Flutterwave encryption.",
            ) from exc

        try:
            key_bytes = base64.b64decode(self.encryption_key)
            cipher = AES.new(key_bytes, AES.MODE_ECB)
            padded_data = data + (16 - len(data) % 16) * chr(16 - len(data) % 16)
            encrypted = cipher.encrypt(padded_data.encode())
            return base64.b64encode(encrypted).decode()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to encrypt Flutterwave payload data.",
            ) from exc

    @classmethod
    def validate_momo_destination(
        cls,
        account_number: str,
        network: Optional[str] = None,
    ) -> Tuple[str, str, str]:
        local_number = normalize_ghana_number(account_number)
        local_digits = "".join(ch for ch in local_number if ch.isdigit())
        if len(local_digits) != 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only Ghana mobile money numbers are supported for withdrawals.",
            )

        detected_network = detect_flutterwave_network(local_number)
        if detected_network == "UNKNOWN":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only Ghana mobile money numbers are supported for withdrawals.",
            )

        requested_network = cls._normalize_requested_network(network)
        if requested_network and requested_network != detected_network:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Network mismatch. The supplied number resolves to {detected_network}, "
                    f"not {requested_network}."
                ),
            )

        return local_number, normalize_flutterwave_momo_number(local_number), detected_network

    async def initiate_transfer(
        self,
        *,
        account_number: str,
        amount: float,
        currency: str,
        reference: str,
        narration: str,
        beneficiary_name: str,
        network: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if float(amount or 0.0) <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Withdrawal amount must be positive.",
            )

        local_number, flutterwave_number, detected_network = self.validate_momo_destination(
            account_number,
            network=network,
        )

        payload: Dict[str, Any] = {
            "account_bank": detected_network,
            "account_number": flutterwave_number,
            "amount": round(float(amount), 2),
            "currency": str(currency or "GHS").strip().upper() or "GHS",
            "reference": str(reference or "").strip(),
            "narration": str(narration or "CyberCash withdrawal").strip(),
            "beneficiary_name": str(beneficiary_name or "CyberCash").strip(),
        }
        if meta:
            payload["meta"] = meta

        headers = await self._get_auth_headers()

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(f"{self.base_url}/transfers", headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Flutterwave returned an unexpected response.",
                    )

                api_status = str(data.get("status") or "").strip().lower()
                transfer_data = data.get("data") or {}
                transfer_status = str(transfer_data.get("status") or "").strip().upper()

                if api_status not in {"success", "successful", "ok"}:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=str(data.get("message") or "Flutterwave rejected the transfer request."),
                    )

                return {
                    "status": api_status,
                    "message": data.get("message") or "Flutterwave transfer accepted.",
                    "data": transfer_data,
                    "payload": payload,
                    "local_account_number": local_number,
                    "flutterwave_account_number": flutterwave_number,
                    "detected_network": detected_network,
                    "transfer_status": transfer_status,
                }
        except HTTPException:
            raise
        except httpx.HTTPStatusError as exc:
            provider_message = self._extract_error_message(exc.response)
            if 400 <= exc.response.status_code < 500:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Flutterwave rejected request: {provider_message}",
                )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Flutterwave service unavailable: {provider_message}",
            )
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Flutterwave network error: {exc}",
            )

    async def verify_transfer(self, transfer_id: str) -> Dict[str, Any]:
        transfer_id = str(transfer_id or "").strip()
        if not transfer_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transfer ID is required.",
            )

        headers = await self._get_auth_headers()

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(f"{self.base_url}/transfers/{transfer_id}", headers=headers)
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Flutterwave returned an unexpected response.",
                    )
                return data
        except HTTPException:
            raise
        except httpx.HTTPStatusError as exc:
            provider_message = self._extract_error_message(exc.response)
            if 400 <= exc.response.status_code < 500:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Flutterwave verification rejected: {provider_message}",
                )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Flutterwave service unavailable: {provider_message}",
            )
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Flutterwave network error: {exc}",
            )


_flutterwave_service = FlutterwaveService()


def get_flutterwave_service() -> FlutterwaveService:
    return _flutterwave_service
