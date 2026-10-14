from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import User
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
    if otp_code and str(os.getenv("RUNNING_TESTS", "")).strip().lower() == "true":
        payload["debug_otp"] = str(otp_code)
    return payload


def _raise_if_otp_dispatch_failed(send_result: dict | None) -> None:
    if isinstance(send_result, dict) and str(send_result.get("status", "") or "").strip().lower() == "queued":
        return

    detail = str((send_result or {}).get("detail", "") or "").strip()
    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail or "Unable to send OTP by email.")


async def _resolve_recipient_email(
    db: AsyncSession,
    identity: str,
    purpose: str,
    supplied_email: str | None,
) -> str:
    result = await db.execute(
        select(User).filter(or_(User.momo_number == identity, User.phone_number == identity))
    )
    user = result.scalars().one_or_none()
    if user:
        email = str(user.email or "").strip().lower()
    elif purpose == "register":
        email = str(supplied_email or "").strip().lower()
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A valid account email is required to receive an OTP.",
        )
    return email


@router.post("/send")
async def send_otp(
    data: OTPSendSchema,
    request: Request,
    db: AsyncSession = Depends(get_db),
    otp_service: OTPService = Depends(get_otp_service),
):
    identity = _normalize_identity_number(data.momo_number)
    _enforce_rate_limit("otp_send", identity, request.client.host if request.client else None)
    recipient_email = await _resolve_recipient_email(db, identity, data.purpose.value, data.email)

    otp_code, send_result = await otp_service.issue_otp(
        identity,
        purpose=data.purpose.value,
        recipient_email=recipient_email,
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
    db: AsyncSession = Depends(get_db),
    otp_service: OTPService = Depends(get_otp_service),
):
    identity = _normalize_identity_number(data.momo_number)
    _enforce_rate_limit("otp_resend", identity, request.client.host if request.client else None)
    recipient_email = await _resolve_recipient_email(db, identity, data.purpose.value, data.email)

    otp_code, send_result = await otp_service.resend_otp(
        identity,
        purpose=data.purpose.value,
        recipient_email=recipient_email,
    )
    _raise_if_otp_dispatch_failed(send_result)
    return _with_debug_otp({"message": "OTP resent"}, otp_service, otp_code)
