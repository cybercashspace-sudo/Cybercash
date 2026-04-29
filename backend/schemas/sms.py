from typing import Optional

from pydantic import BaseModel, Field


class SMSRequest(BaseModel):
    phone: str = Field(..., min_length=6, max_length=20)
    message: str = Field(..., min_length=1, max_length=500)
    sms_type: Optional[str] = Field(default=None, max_length=32)
