from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class CryptoTransactionBase(BaseModel):
    user_id: int
    crypto_wallet_id: Optional[int] = None
    coin_type: str
    type: str # 'deposit' or 'withdrawal'
    amount: float
    transaction_hash: Optional[str] = None
    from_address: Optional[str] = None
    to_address: Optional[str] = None
    fee: float = 0.0
    status: str = "pending"

class CryptoTransactionCreate(CryptoTransactionBase):
    pass

class CryptoTransactionResponse(CryptoTransactionBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
