from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class LoanBase(BaseModel):
    amount: float
    outstanding_balance: float
    repayment_due_date: datetime
    status: str

class LoanCreate(LoanBase):
    agent_id: int
    application_id: int
    # disbursement_date: datetime # Set by service

class LoanUpdate(BaseModel):
    outstanding_balance: Optional[float] = None
    status: Optional[str] = None
    repayment_date: Optional[datetime] = None

class LoanInDB(LoanBase):
    id: int
    user_id: Optional[int] = None
    agent_id: Optional[int] = None
    application_id: int
    repayment_duration: Optional[int] = None
    base_fee_percentage: float = 0.0
    base_fee_amount: float = 0.0
    late_fee_percentage: float = 0.0
    late_fee_amount: float = 0.0
    late_fee_applied_at: Optional[datetime] = None
    disbursement_date: datetime
    repayment_date: Optional[datetime] = None
    remaining_balance: float = 0.0
    total_fee_amount: float = 0.0
    total_due: float = 0.0
    late_fee_applied: bool = False
    is_overdue: bool = False
    owner_type: str = "user"
    manual_repayment_allowed: bool = True
    manual_repayment_message: str = ""

    class Config:
        from_attributes = True


class LoanPolicyResponse(BaseModel):
    allowed_periods: list[int]
    is_agent_eligible: bool
    auto_deduction_enabled: bool = True
    base_fee_percentage: float
    late_fee_percentage: float
    late_fee_grace_hours: int
    period_help_text: str
    fee_help_text: str


class LoanAutoDeductionUpdateRequest(BaseModel):
    enabled: bool


class LoanAutoDeductionResponse(BaseModel):
    agent_id: int
    enabled: bool
