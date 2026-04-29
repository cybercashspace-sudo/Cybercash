from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class AgentDataOrderRequest(BaseModel):
    network: str = Field(..., min_length=2, max_length=20)
    phone: str = Field(..., min_length=6, max_length=20)
    bundle_id: int = Field(..., gt=0)


class DataOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: int
    agent_id: Optional[int] = None
    bundle_catalog_id: Optional[int] = None

    network: str
    phone: str
    bundle_id: int

    amount: float
    currency: str
    status: str
    status_label: Optional[str] = None
    provider: str
    provider_reference: Optional[str] = None
    provider_response_json: Optional[str] = None

    created_at: datetime


class AgentDataOrderPurchaseResponse(BaseModel):
    order: DataOrderResponse
    transaction_id: int
    payment_id: int
    provider_response: dict[str, Any]
