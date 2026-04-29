from pydantic import BaseModel, Field, field_validator
from typing import Optional
import re

class RegisterSchema(BaseModel):
    momo_number: str = Field(..., min_length=8, max_length=20)
    email: Optional[str] = Field(default=None, min_length=5, max_length=254)
    phone_number: Optional[str] = Field(default=None, min_length=8, max_length=20)
    pin: str = Field(..., min_length=4, max_length=4)
    device_id: Optional[str] = Field(default=None, min_length=1, max_length=128)
    device_fingerprint: Optional[str] = Field(default=None, min_length=8, max_length=256)
    full_name: Optional[str] = ""
    first_name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    is_agent: bool = False
    business_name: Optional[str] = None
    ghana_card_id: Optional[str] = None
    agent_location: Optional[str] = None

    @field_validator("pin")
    @classmethod
    def pin_must_be_4_digits(cls, value: str) -> str:
        if not re.fullmatch(r"\d{4}", value or ""):
            raise ValueError("PIN must be exactly 4 digits.")
        return value

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        email = str(value or "").strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise ValueError("Email must be a valid email address.")
        return email

class LoginSchema(BaseModel):
    momo_number: Optional[str] = Field(default=None, min_length=8, max_length=20)
    phone_number: Optional[str] = Field(default=None, min_length=8, max_length=20)
    pin: Optional[str] = Field(default=None, min_length=4, max_length=4)
    password: Optional[str] = Field(default=None, min_length=4, max_length=128)
    device_id: Optional[str] = Field(default=None, min_length=1, max_length=128)
    device_fingerprint: Optional[str] = Field(default=None, min_length=8, max_length=256)

    @field_validator("pin")
    @classmethod
    def pin_must_be_4_digits(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        if not re.fullmatch(r"\d{4}", value or ""):
            raise ValueError("PIN must be exactly 4 digits.")
        return value

class VerifyOtpSchema(BaseModel):
    momo_number: str = Field(..., min_length=8, max_length=20)
    phone_number: Optional[str] = Field(default=None, min_length=8, max_length=20)
    otp_code: str = Field(..., min_length=4, max_length=6)

    @field_validator("otp_code")
    @classmethod
    def otp_must_be_6_digits(cls, value: str) -> str:
        if not re.fullmatch(r"\d{4,6}", value or ""):
            raise ValueError("OTP must be 4 to 6 digits.")
        return value


class ChangePinSchema(BaseModel):
    old_pin: str = Field(..., min_length=4, max_length=4)
    new_pin: str = Field(..., min_length=4, max_length=4)
    device_fingerprint: Optional[str] = Field(default=None, min_length=8, max_length=256)

    @field_validator("old_pin", "new_pin")
    @classmethod
    def pin_must_be_4_digits(cls, value: str) -> str:
        if not re.fullmatch(r"\d{4}", value or ""):
            raise ValueError("PIN must be exactly 4 digits.")
        return value


class ResetPinRequestSchema(BaseModel):
    momo_number: str = Field(..., min_length=8, max_length=20)


class ResetPinSchema(BaseModel):
    momo_number: str = Field(..., min_length=8, max_length=20)
    otp: str = Field(..., min_length=4, max_length=6)
    new_pin: str = Field(..., min_length=4, max_length=4)
    device_fingerprint: Optional[str] = Field(default=None, min_length=8, max_length=256)

    @field_validator("otp")
    @classmethod
    def otp_must_be_6_digits(cls, value: str) -> str:
        if not re.fullmatch(r"\d{4,6}", value or ""):
            raise ValueError("OTP must be 4 to 6 digits.")
        return value

    @field_validator("new_pin")
    @classmethod
    def pin_must_be_4_digits(cls, value: str) -> str:
        if not re.fullmatch(r"\d{4}", value or ""):
            raise ValueError("PIN must be exactly 4 digits.")
        return value


class AccessSchema(BaseModel):
    momo_number: str = Field(..., min_length=8, max_length=20)
    pin: str = Field(..., min_length=4, max_length=4)
    first_name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    is_agent: bool = False
    device_id: Optional[str] = Field(default=None, min_length=1, max_length=128)
    device_fingerprint: Optional[str] = Field(default=None, min_length=8, max_length=256)

    @field_validator("pin")
    @classmethod
    def pin_must_be_4_digits(cls, value: str) -> str:
        if not re.fullmatch(r"\d{4}", value or ""):
            raise ValueError("PIN must be exactly 4 digits.")
        return value


class VerifySchema(BaseModel):
    momo_number: str = Field(..., min_length=8, max_length=20)
    otp: str = Field(..., min_length=4, max_length=6)

    @field_validator("otp")
    @classmethod
    def otp_must_be_6_digits(cls, value: str) -> str:
        if not re.fullmatch(r"\d{4,6}", value or ""):
            raise ValueError("OTP must be 4 to 6 digits.")
        return value


class ResendSchema(BaseModel):
    momo_number: str = Field(..., min_length=8, max_length=20)


class LookupNameSchema(BaseModel):
    momo_number: str = Field(..., min_length=8, max_length=20)


class LookupNameResponse(BaseModel):
    registered: bool
    momo_number: str
    network: str
    first_name: Optional[str] = ""
    full_name: Optional[str] = ""
    display_name: str
    is_verified: bool = False


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None
