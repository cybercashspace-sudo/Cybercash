from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class ExchangeRequest(BaseModel):
    from_currency: str
    to_currency: str
    amount: float # Amount in from_currency

class ExchangeResponse(BaseModel):
    transaction_id: int
    from_currency: str
    to_currency: str
    amount_sent: float
    amount_received: float
    exchange_rate: float
    spread_amount: Optional[float] = None
    message: str