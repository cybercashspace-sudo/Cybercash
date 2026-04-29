from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class LoanOverviewResponse(BaseModel):
    total_active_loans: int
    total_exposure: float
    default_risk_percentage: float
    repayment_rate: float
    # agent_risk_heatmap: dict # This would be more complex, placeholder for now

class AgentCreditProfileResponse(BaseModel):
    agent_id: int
    user_id: int
    full_name: Optional[str] = None
    email: Optional[str] = None
    credit_score: Optional[int] = None
    max_eligible_loan_amount: float
    current_loan_id: Optional[int] = None
    current_loan_amount: Optional[float] = None
    current_loan_outstanding_balance: Optional[float] = None
    repayment_progress_percentage: Optional[float] = None
    risk_flags: List[str] # e.g., ["high_default_risk", "inactivity_alert"]

class LoanPolicyUpdateRequest(BaseModel):
    max_loan_amount_per_agent: Optional[float] = None
    default_penalty_fee_percentage: Optional[float] = None
    risk_score_approval_threshold: Optional[int] = None
    # More detailed settings like interest range, duration limits, etc. could be added here


class LoanApplicationDecisionRequest(BaseModel):
    decision: str = Field(..., pattern="^(approved|rejected)$")
    approved_amount: Optional[float] = Field(default=None, gt=0)
    fee_percentage: Optional[float] = Field(default=None, ge=0)
    offered_repayment_duration: Optional[int] = Field(default=None, gt=0)
    review_note: Optional[str] = None
