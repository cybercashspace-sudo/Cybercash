from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AirtimePurchaseRequest(BaseModel):
    network: str = Field(..., min_length=2, max_length=20)
    phone: str = Field(..., min_length=6, max_length=20)
    amount: float = Field(..., ge=1)


class AirtimeCashQuoteRequest(BaseModel):
    phone: str = Field(..., min_length=6, max_length=20)
    network: str = Field(..., min_length=2, max_length=20)
    amount: float = Field(..., gt=0)
    currency: str = Field(default="GHS", min_length=2, max_length=10)


class AirtimeCashQuoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sale_id: str
    merchant_number: str
    payout_rate: float
    payout_amount: float
    fee_amount: float
    status: str
    instructions: str


class AirtimeCashConfirmRequest(BaseModel):
    sale_id: str = Field(..., min_length=8, max_length=64)


class AirtimeCashSaleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: int
    phone: str
    network: str
    amount: float
    payout_amount: float
    payout_rate: float
    currency: str
    status: str
    merchant_number: str
    created_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None


class AirtimeCashSmsWebhook(BaseModel):
    sender: Optional[str] = None
    message: str = Field(..., min_length=3)
    received_at: Optional[datetime] = None
