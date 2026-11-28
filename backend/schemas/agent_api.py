from decimal import Decimal

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CreateAgentAPIKeyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=60)
    mode: Literal["test", "live"] = "live"


class AgentCheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: Decimal = Field(gt=0, le=Decimal("10000.00"))
    customer_email: str = Field(min_length=5, max_length=254)


class AgentCheckoutResponse(BaseModel):
    status: str
    reference: str
    authorization_url: str | None = None
    amount: Decimal
    currency: str = "GHS"
