from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class PaymentBase(BaseModel):
    user_id: int
    processor: str
    type: str
    amount: float
    currency: str = "GHS"
    agent_id: Optional[int] = None
    status: str = "pending"
    processor_transaction_id: Optional[str] = None
    our_transaction_id: Optional[str] = None
    metadata_json: Optional[str] = None

class PaymentCreate(PaymentBase):
    pass

class PaymentResponse(PaymentBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
