from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class CryptoWalletBase(BaseModel):
    user_id: int
    coin_type: str
    address: str
    balance: float = 0.0
    is_active: bool = True

class CryptoWalletCreate(BaseModel):
    coin_type: str # User requests a wallet for a specific coin_type

class CryptoWalletResponse(CryptoWalletBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime
