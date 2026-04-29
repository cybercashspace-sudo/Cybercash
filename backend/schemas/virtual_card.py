from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Literal
from datetime import datetime

class VirtualCardBase(BaseModel):
    currency: str = Field("USD", min_length=3, max_length=3)
    type: Literal["one-time", "rechargeable"] = "rechargeable"
    spending_limit: float = Field(0.0, ge=0) # Can be set when requesting, 0 for no limit

class VirtualCardCreate(VirtualCardBase):
    pass

class VirtualCardLoadFunds(BaseModel):
    amount: float = Field(..., gt=0)

class VirtualCardUpdateLimit(BaseModel):
    spending_limit: float = Field(..., ge=0)

class VirtualCardStatusUpdate(BaseModel):
    status: Literal["active", "blocked"] = "active"

class VirtualCardInDB(VirtualCardBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    card_number: str
    expiry_date: str
    cvv_hashed: str # Should be handled securely on frontend/backend, not exposed directly
    balance: float
    status: str
    issuance_fee_paid: float
    provider_card_id: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class CardProcessorAuthorizationRequest(BaseModel):
    provider_card_id: Optional[str] = Field(default=None, min_length=1, max_length=128)
    card_number: Optional[str] = Field(default=None, min_length=12, max_length=19)
    amount: float = Field(..., gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=10)
    merchant_name: str = Field(..., min_length=1, max_length=120)
    merchant_country: Optional[str] = Field(default=None, min_length=2, max_length=2)
    fee: float = Field(default=0.0, ge=0)
    fx_margin: float = Field(default=0.0, ge=0)
    processor_reference: Optional[str] = Field(default=None, min_length=1, max_length=128)


class CardProcessorAuthorizationResponse(BaseModel):
    approved: bool
    status: str
    reason: Optional[str] = None
    transaction_id: Optional[int] = None
    wallet_balance_after: Optional[float] = None

