from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class TransactionSecurityContext(BaseModel):
    pin_verified: bool = False
    biometric_verified: bool = False
    device_fingerprint: Optional[str] = None
    ip_address: Optional[str] = None
    channel: Optional[str] = None
    daily_limit: Optional[float] = Field(default=None, gt=0)
    biometric_threshold: Optional[float] = Field(default=None, gt=0)
    risk_override: bool = False


class AirtimePurchaseRequest(TransactionSecurityContext):
    amount: float = Field(..., gt=0)
    network: str = Field(..., min_length=2, max_length=20)
    phone_number: str = Field(..., min_length=6, max_length=20)
    provider: Optional[str] = None
    cost_price: Optional[float] = Field(default=None, ge=0)


class DataPurchaseRequest(TransactionSecurityContext):
    amount: float = Field(..., gt=0)
    network: str = Field(..., min_length=2, max_length=20)
    phone_number: str = Field(..., min_length=6, max_length=20)
    bundle_code: str = Field(..., min_length=1, max_length=64)
    provider: Optional[str] = None
    cost_price: Optional[float] = Field(default=None, ge=0)


class EscrowCreateRequest(TransactionSecurityContext):
    amount: float = Field(..., gt=0)
    recipient_wallet_id: str = Field(..., min_length=10, max_length=15)
    fee: float = Field(default=0.0, ge=0)
    description: Optional[str] = None


class EscrowReleaseRequest(TransactionSecurityContext):
    amount: float = Field(..., gt=0)
    escrow_deal_id: Optional[int] = Field(default=None, gt=0)
    recipient_user_id: Optional[int] = Field(default=None, gt=0)
    fee: float = Field(default=0.0, ge=0)
    release_note: Optional[str] = None


class InvestmentCreateRequest(TransactionSecurityContext):
    amount: float = Field(..., ge=10)
    plan_name: Optional[str] = None
    duration_days: Optional[int] = Field(default=None, ge=7, le=365)
    expected_rate: Optional[float] = Field(default=None, ge=0)


class InvestmentPayoutRequest(TransactionSecurityContext):
    amount: float = Field(default=0.0, ge=0)
    investment_id: Optional[int] = Field(default=None, gt=0)
    gain: float = Field(default=0.0, ge=0)
    plan_name: Optional[str] = None


class CardSpendRequest(TransactionSecurityContext):
    amount: float = Field(..., gt=0)
    card_id: Optional[int] = None
    merchant_name: str = Field(..., min_length=1, max_length=120)
    merchant_country: Optional[str] = Field(default=None, min_length=2, max_length=2)
    fee: float = Field(default=0.0, ge=0)
    fx_margin: float = Field(default=0.0, ge=0)
    use_card_balance: bool = False
    extra_metadata: Optional[Dict[str, Any]] = None
