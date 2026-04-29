from pydantic import BaseModel, ConfigDict
from typing import Optional

class VirtualCardBase(BaseModel):
    user_id: int
    card_number: str
    balance: float
    status: str

class VirtualCardCreate(BaseModel):
    balance: float = 0.0 # Optional initial balance. Default to 0.0

class VirtualCardResponse(VirtualCardBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
