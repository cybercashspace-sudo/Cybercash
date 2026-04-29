from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class LoanApplicationBase(BaseModel):
    amount: float
    repayment_duration: int
    purpose: Optional[str] = None

class LoanApplicationCreate(LoanApplicationBase):
    pass

class LoanApplicationUpdate(LoanApplicationBase):
    status: Optional[str] = None
    risk_score: Optional[int] = None
    approved_date: Optional[datetime] = None
    rejected_date: Optional[datetime] = None
    approved_amount: Optional[float] = None
    fee_percentage: Optional[float] = None
    offered_repayment_duration: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    reviewed_by_admin_id: Optional[int] = None
    review_note: Optional[str] = None

class LoanApplicationInDB(LoanApplicationBase):
    id: int
    user_id: Optional[int] = None
    agent_id: Optional[int] = None
    status: str
    application_date: datetime
    risk_score: Optional[int] = None
    approved_date: Optional[datetime] = None
    rejected_date: Optional[datetime] = None
    approved_amount: Optional[float] = None
    fee_percentage: Optional[float] = None
    offered_repayment_duration: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    reviewed_by_admin_id: Optional[int] = None
    review_note: Optional[str] = None

class Config:
        from_attributes = True
