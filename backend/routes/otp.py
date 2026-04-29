from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status

from backend.schemas.otp import OTPSendSchema, OTPVerifySchema, OTPResendSchema
from backend.services.otp_service import OTPService, get_otp_service
from utils.network import normalize_ghana_number


router = APIRouter(prefix="/otp", tags=["OTP"])
logger = logging.getLogger(__name__)

_RATE_LIMIT_STATE: dict[str, list[datetime]] = {}
_RATE_LIMIT_WINDOW_SECONDS = 300
_RATE_LIMIT_MAX_ATTEMPTS = 5


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_identity_number(raw_number: str | None) -> str:
    normalized = normalize_ghana_number(raw_number or "")
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="momo_number is required")
    return normalized


def _enforce_rate_limit(action: str, identity: str, ip_address: str | None = None) -> None:
    key = f"{action}:{identity}:{ip_address or 'unknown'}"
    now = _now_utc()
    window_start = now - timedelta(seconds=_RATE_LIMIT_WINDOW_SECONDS)
    attempts = _RATE_LIMIT_STATE.get(key, [])
    attempts = [ts for ts in attempts if ts >= window_start]
    if len(attempts) >= _RATE_LIMIT_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please try again later.",
        )
    attempts.append(now)
    _RATE_LIMIT_STATE[key] = attempts


def _with_debug_otp(payload: dict, otp_service: OTPService, otp_code: str | None) -> dict:
    if otp_code and otp_service.provider == "log":
        payload["debug_otp"] = str(otp_code)
    return payload


def _raise_if_otp_dispatch_failed(send_result: dict | None) -> None:
    if not isinstance(send_result, dict):
        return
    status_value = str(send_result.get("status", "") or "").strip().lower()
    if status_value != "error":
        return

    detail = str(send_result.get("detail", "") or "").strip()
    if detail:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)
    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to send OTP right now.")


@router.post("/send")
async def send_otp(
    data: OTPSendSchema,
    request: Request,
    otp_service: OTPService = Depends(get_otp_service),
):
    identity = _normalize_identity_number(data.momo_number)
    _enforce_rate_limit("otp_send", identity, request.client.host if request.client else None)

    otp_code, send_result = await otp_service.issue_otp(
        identity,
        purpose=data.purpose.value,
        recipient_email=data.email,
    )
    _raise_if_otp_dispatch_failed(send_result)
    return _with_debug_otp({"message": "OTP sent"}, otp_service, otp_code)


@router.post("/verify")
async def verify_otp(
    data: OTPVerifySchema,
    request: Request,
    otp_service: OTPService = Depends(get_otp_service),
):
    identity = _normalize_identity_number(data.momo_number)
    _enforce_rate_limit("otp_verify", identity, request.client.host if request.client else None)

    ok = await otp_service.verify_otp(identity, data.otp, purpose=data.purpose.value)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP")
    return {"message": "OTP verified"}


@router.post("/resend")
async def resend_otp(
    data: OTPResendSchema,
    request: Request,
    otp_service: OTPService = Depends(get_otp_service),
):
    identity = _normalize_identity_number(data.momo_number)
    _enforce_rate_limit("otp_resend", identity, request.client.host if request.client else None)

    otp_code, send_result = await otp_service.resend_otp(
        identity,
        purpose=data.purpose.value,
        recipient_email=data.email,
    )
    _raise_if_otp_dispatch_failed(send_result)
    return _with_debug_otp({"message": "OTP resent"}, otp_service, otp_code)
