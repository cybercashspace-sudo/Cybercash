from typing import Optional

from pydantic import BaseModel, Field, model_validator


class SMSRequest(BaseModel):
    phone: Optional[str] = Field(default=None, min_length=6, max_length=20)
    recipients: list[str] = Field(default_factory=list)
    user_ids: list[int] = Field(default_factory=list)
    message: str = Field(..., min_length=1, max_length=500)
    sms_type: Optional[str] = Field(default=None, max_length=32)
    is_schedule: bool = False
    schedule_date: str = ""

    @model_validator(mode="after")
    def recipients_must_exist(self):
        if self.phone or self.recipients or self.user_ids:
            return self
        raise ValueError("Provide phone, recipients, or user_ids.")
