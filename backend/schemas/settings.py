from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _normalize_text(value: str | None, default: str) -> str:
    text = str(value or "").strip()
    return text or default


class UserSettingsUpdate(BaseModel):
    biometric: Optional[bool] = None
    otp: Optional[bool] = None
    auto_settle: Optional[bool] = None
    sms_alerts: Optional[bool] = None
    email_alerts: Optional[bool] = None
    transaction_pin: Optional[bool] = None
    device_binding: Optional[bool] = None
    login_alerts: Optional[bool] = None
    push_notifications: Optional[bool] = None
    fraud_alerts: Optional[bool] = None
    withdrawal_limit: Optional[float] = Field(default=None, ge=0)
    default_payout_method: Optional[str] = None
    preferred_currency: Optional[str] = None
    fee_display: Optional[bool] = None

    @field_validator("default_payout_method")
    @classmethod
    def normalize_default_payout_method(cls, value: Optional[str]) -> str:
        return _normalize_text(value, "momo").lower()

    @field_validator("preferred_currency")
    @classmethod
    def normalize_preferred_currency(cls, value: Optional[str]) -> str:
        return _normalize_text(value, "GHS").upper()


class UserSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    biometric: bool = False
    otp: bool = True
    auto_settle: bool = True
    sms_alerts: bool = True
    email_alerts: bool = False
    transaction_pin: bool = True
    device_binding: bool = True
    login_alerts: bool = True
    push_notifications: bool = False
    fraud_alerts: bool = True
    withdrawal_limit: float = 2000.0
    default_payout_method: str = "momo"
    preferred_currency: str = "GHS"
    fee_display: bool = True
    updated_at: Optional[datetime] = None


class PlatformSettingsUpdate(BaseModel):
    agent_registration_fee: Optional[float] = Field(default=None, ge=0)
    platform_fee_percentage: Optional[float] = Field(default=None, ge=0, le=1)
    withdrawal_limit: Optional[float] = Field(default=None, ge=0)
    fraud_threshold: Optional[float] = Field(default=None, ge=0)
    commission_rate: Optional[float] = Field(default=None, ge=0, le=1)


class PlatformSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_registration_fee: float = 100.0
    platform_fee_percentage: float = 0.01
    withdrawal_limit: float = 1000.0
    fraud_threshold: float = 1000.0
    commission_rate: float = 0.02
    updated_by_user_id: Optional[int] = None
    updated_at: Optional[datetime] = None
