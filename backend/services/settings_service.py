from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings as app_settings
from backend.models import PlatformSettings, UserSettings


DEFAULT_USER_SETTINGS: dict[str, Any] = {
    "biometric": False,
    "otp": True,
    "auto_settle": True,
    "sms_alerts": True,
    "email_alerts": False,
    "transaction_pin": True,
    "device_binding": True,
    "login_alerts": True,
    "push_notifications": False,
    "fraud_alerts": True,
    "withdrawal_limit": 2000.0,
    "default_payout_method": "momo",
    "preferred_currency": "GHS",
    "fee_display": True,
}

DEFAULT_PLATFORM_SETTINGS: dict[str, Any] = {
    "agent_registration_fee": float(getattr(app_settings, "AGENT_REGISTRATION_FEE", 100.0) or 100.0),
    "platform_fee_percentage": float(getattr(app_settings, "TRANSACTION_FEE_PERCENTAGE", 0.01) or 0.01),
    "withdrawal_limit": float(getattr(app_settings, "WITHDRAWAL_APPROVAL_THRESHOLD_GHS", 1000.0) or 1000.0),
    "fraud_threshold": float(getattr(app_settings, "WITHDRAWAL_APPROVAL_THRESHOLD_GHS", 1000.0) or 1000.0),
    "commission_rate": float(getattr(app_settings, "AGENT_COMMISSION_RATE", 0.02) or 0.02),
}

ALLOWED_PAYOUT_METHODS = {"momo", "bank", "crypto"}


def normalize_payout_method(value: str | None) -> str:
    method = str(value or "").strip().lower()
    return method if method in ALLOWED_PAYOUT_METHODS else "momo"


def normalize_currency(value: str | None) -> str:
    currency = str(value or "").strip().upper()
    return currency or "GHS"


async def get_or_create_user_settings(db: AsyncSession, user_id: int) -> UserSettings:
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    row = result.scalar_one_or_none()
    if row is not None:
        return row

    row = UserSettings(user_id=user_id, **DEFAULT_USER_SETTINGS)
    db.add(row)
    await db.flush()
    return row


async def get_or_create_platform_settings(db: AsyncSession) -> PlatformSettings:
    result = await db.execute(select(PlatformSettings).order_by(PlatformSettings.id.asc()))
    row = result.scalars().first()
    if row is not None:
        return row

    row = PlatformSettings(**DEFAULT_PLATFORM_SETTINGS)
    db.add(row)
    await db.flush()
    return row


def resolve_effective_withdrawal_limit(user, user_settings: UserSettings | None = None, platform_settings: PlatformSettings | None = None) -> float:
    limits: list[float] = []
    for raw_value in (
        getattr(user, "daily_limit", None),
        getattr(user_settings, "withdrawal_limit", None),
        getattr(platform_settings, "withdrawal_limit", None),
    ):
        try:
            value = float(raw_value or 0.0)
        except (TypeError, ValueError):
            continue
        if value > 0:
            limits.append(value)

    if not limits:
        return 0.0
    return min(limits)
