import os
import time
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies.auth import get_current_user
from backend.database import get_db
from backend.models import User
from backend.schemas.sms import SMSRequest
from backend.services.sms_service import get_sms_service


router = APIRouter(prefix="/api/sms", tags=["SMS"])
sms_service = get_sms_service()

_rate_limit_bucket: Dict[str, List[float]] = {}
_rate_limit_max = int(os.getenv("SMS_RATE_LIMIT_PER_HOUR", "5"))
_rate_limit_window = int(os.getenv("SMS_RATE_LIMIT_WINDOW_SECONDS", "3600"))


def _check_rate_limit(identity: str) -> None:
    now = time.time()
    window_start = now - _rate_limit_window
    history = [ts for ts in _rate_limit_bucket.get(identity, []) if ts >= window_start]
    if len(history) >= _rate_limit_max:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="SMS rate limit exceeded. Try again later.",
        )
    history.append(now)
    _rate_limit_bucket[identity] = history


@router.post("/send", status_code=status.HTTP_200_OK)
async def send_sms_api(
    payload: SMSRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    message = str(payload.message or "").strip()
    if not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message is required.")

    recipients: list[str] = []
    if payload.phone:
        phone = sms_service.format_recipient(payload.phone, provider=sms_service.provider)
        if not phone:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a valid phone number.")
        recipients.append(phone)

    if payload.recipients:
        for phone in payload.recipients:
            normalized = sms_service.format_recipient(phone, provider=sms_service.provider)
            if normalized:
                recipients.append(normalized)

    if payload.user_ids:
        result = await db.execute(select(User).where(User.id.in_(payload.user_ids)))
        users = result.scalars().all()
        for user in users:
            number = sms_service.format_recipient(
                str(user.momo_number or user.phone_number or ""),
                provider=sms_service.provider,
            )
            if number:
                recipients.append(number)

    if not recipients:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide at least one recipient.")

    identity = str(current_user.id or recipients[0])
    _check_rate_limit(identity)

    result = sms_service.send_bulk_sms(
        recipients,
        message,
        sms_type=payload.sms_type,
        is_schedule=payload.is_schedule,
        schedule_date=payload.schedule_date,
    )
    if isinstance(result, dict) and result.get("status") == "error":
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=result.get("detail", "SMS failed."))
    return {
        "status": "queued",
        "provider": sms_service.provider,
        "result": result,
        "recipient_count": len(result.get("recipients", recipients)),
    }
