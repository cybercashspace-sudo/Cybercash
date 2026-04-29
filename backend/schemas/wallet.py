from pydantic import BaseModel, ConfigDict, Field
from typing import Literal, Optional
from datetime import datetime

class TransferFundsRequest(BaseModel):
    recipient_wallet_id: str = Field(..., min_length=10, max_length=16)
    amount: float
    currency: str = "GHS" # Default to Ghanaian Cedis
    source_balance: Literal["balance", "escrow_balance", "loan_balance", "investment_balance"] = "balance"
    recipient_must_be_agent: bool = False

class WalletBase(BaseModel):
    user_id: int
    currency: str
    balance: float

class WalletResponse(WalletBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    escrow_balance: float = 0.0
    loan_balance: float = 0.0
    investment_balance: float = 0.0
    created_at: datetime
    updated_at: datetime
    metadata_json: Optional[str] = None # Include metadata_json in response


class TransferFundsResponse(WalletResponse):
    transfer_reference: str
    recipient_wallet_id: str
    source_balance: Literal["balance", "escrow_balance", "loan_balance", "investment_balance"] = "balance"
    recipient_is_agent: bool = False
    transfer_fee: float = 0.0
    transfer_fee_rate: float = 0.0
    total_debited: float = 0.0
    p2p_daily_free_limit: float = 0.0
    p2p_total_sent_today_before: float = 0.0
    p2p_free_remaining_before: float = 0.0
    p2p_fee_free_amount: float = 0.0
    p2p_feeable_amount: float = 0.0

class WalletCreate(WalletBase):
    pass


class InvestmentReinvestToggleRequest(BaseModel):
    enabled: bool


class InvestmentReinvestToggleResponse(BaseModel):
    wallet_id: int
    enabled: bool
