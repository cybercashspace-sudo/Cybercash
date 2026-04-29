from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Literal

class WithdrawalApprovalRequest(BaseModel):
    status: Literal["approved", "rejected"]
    reason: Optional[str] = None

class BankWithdrawalInitiateRequest(BaseModel):
    amount: float = Field(..., gt=0)
    currency: str = Field(..., min_length=2, max_length=10)
    bank_name: str = Field(..., min_length=1)
    account_name: str = Field(..., min_length=1)
    account_number: str = Field(..., min_length=1)
    swift_code: Optional[str] = None
    notes: Optional[str] = None

class MomoWithdrawalInitiateRequest(BaseModel):
    amount: float = Field(..., gt=0)
    currency: str = Field(..., min_length=2, max_length=10)
    phone_number: str = Field(..., min_length=1)
    network: Optional[str] = Field(default=None, min_length=1, max_length=20) # Optional; backend auto-detects network.
    notes: Optional[str] = None

class AdminCryptoWithdrawalInitiateRequest(BaseModel):
    amount: float = Field(..., gt=0)
    currency: str = Field(..., min_length=2, max_length=10) # e.g., "USD", "GHS" - for tracking equivalent value
    coin_type: str = Field(..., min_length=1) # e.g., "BTC", "ETH", "USDT"
    to_address: str = Field(..., min_length=1)
    fee: Optional[float] = Field(0.0, ge=0) # Optional, admin might set fee for manual withdrawal
    notes: Optional[str] = None

class AgentBorrowingFreezeRequest(BaseModel):
    is_borrowing_frozen: bool

class WalletFreezeRequest(BaseModel):
    is_frozen: bool


class UserStatusUpdateRequest(BaseModel):
    status: Literal["active", "suspended"]

