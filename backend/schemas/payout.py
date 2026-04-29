from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from utils.network import normalize_ghana_number


class WithdrawalRequest(BaseModel):
    user_id: Optional[int] = None
    amount: float = Field(..., gt=0)
    method: Literal["momo"] = "momo"
    account_number: str = Field(..., min_length=8, max_length=20)
    network: Optional[str] = Field(default=None, min_length=1, max_length=20)
    currency: str = Field(default="GHS", min_length=3, max_length=10)
    notes: Optional[str] = None

    @model_validator(mode="after")
    def normalize_fields(self):
        self.account_number = normalize_ghana_number(self.account_number)
        self.currency = str(self.currency or "GHS").strip().upper() or "GHS"
        if self.network is not None:
            self.network = str(self.network).strip().upper() or None
        return self
