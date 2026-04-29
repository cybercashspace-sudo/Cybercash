from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class TransactionBase(BaseModel):
    user_id: int
    wallet_id: int
    type: str
    amount: float
    currency: str = "GHS"
    agent_id: Optional[int] = None
    commission_earned: float = 0.0
    status: str = "pending"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    metadata_json: Optional[str] = None

class TransactionCreate(TransactionBase):
    pass

class TransactionResponse(TransactionBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    timestamp: datetime
