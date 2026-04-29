from __future__ import annotations

import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class OTPPurpose(str, Enum):
    register = "register"
    access_verify = "access_verify"
    reset_pin = "reset_pin"
    ussd_pin = "ussd_pin"


class OTPSendSchema(BaseModel):
    momo_number: str = Field(..., min_length=8, max_length=20)
    purpose: OTPPurpose = OTPPurpose.access_verify
    email: Optional[str] = Field(default=None, max_length=254)


class OTPVerifySchema(BaseModel):
    momo_number: str = Field(..., min_length=8, max_length=20)
    otp: str = Field(..., min_length=4, max_length=6)
    purpose: OTPPurpose = OTPPurpose.access_verify

    @field_validator("otp")
    @classmethod
    def otp_must_be_4_to_6_digits(cls, value: str) -> str:
        if not re.fullmatch(r"\d{4,6}", value or ""):
            raise ValueError("OTP must be 4 to 6 digits.")
        return value


class OTPResendSchema(BaseModel):
    momo_number: str = Field(..., min_length=8, max_length=20)
    purpose: OTPPurpose = OTPPurpose.access_verify
    email: Optional[str] = Field(default=None, max_length=254)
