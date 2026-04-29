from datetime import datetime, timedelta

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.database import Base

class Loan(Base):
    __tablename__ = "loans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), index=True)
    application_id = Column(Integer, ForeignKey("loan_applications.id"), unique=True, index=True)

    amount = Column(Float, nullable=False)
    repayment_duration = Column(Integer, nullable=True)
    base_fee_percentage = Column(Float, default=0.0)
    base_fee_amount = Column(Float, default=0.0)
    late_fee_percentage = Column(Float, default=0.0)
    late_fee_amount = Column(Float, default=0.0)
    late_fee_applied_at = Column(DateTime(timezone=True), nullable=True)
    outstanding_balance = Column(Float, nullable=False)
    repayment_due_date = Column(DateTime(timezone=True), nullable=False)
    status = Column(String, default="active") # e.g., "active", "repaid", "overdue"
    disbursement_date = Column(DateTime(timezone=True), server_default=func.now())
    repayment_date = Column(DateTime(timezone=True), nullable=True) # Actual date of full repayment

    user = relationship("User", back_populates="loans", foreign_keys=[user_id])
    agent = relationship("Agent", back_populates="loans")
    application = relationship("LoanApplication", back_populates="loan")

    @property
    def remaining_balance(self) -> float:
        return float(self.outstanding_balance or 0.0)

    @property
    def total_fee_amount(self) -> float:
        return round(float(self.base_fee_amount or 0.0) + float(self.late_fee_amount or 0.0), 2)

    @property
    def total_due(self) -> float:
        return round(float(self.amount or 0.0) + float(self.total_fee_amount or 0.0), 2)

    @property
    def late_fee_applied(self) -> bool:
        return bool(float(self.late_fee_amount or 0.0) > 0.0)

    @property
    def owner_type(self) -> str:
        return "agent" if self.agent_id else "user"

    @property
    def is_overdue(self) -> bool:
        if str(self.status or "").strip().lower() == "overdue":
            return True
        if str(self.status or "").strip().lower() == "repaid":
            return False
        due_date = self.repayment_due_date
        if due_date is None:
            return False
        now = datetime.utcnow()
        try:
            if due_date.tzinfo is not None:
                now = datetime.now(due_date.tzinfo)
        except Exception:
            now = datetime.utcnow()
        return now > due_date

    @property
    def late_fee_pending(self) -> bool:
        if self.late_fee_applied or str(self.status or "").strip().lower() == "repaid":
            return False
        due_date = self.repayment_due_date
        if due_date is None:
            return False
        now = datetime.utcnow()
        try:
            if due_date.tzinfo is not None:
                now = datetime.now(due_date.tzinfo)
        except Exception:
            now = datetime.utcnow()
        return now >= (due_date + timedelta(hours=24))

    @property
    def manual_repayment_allowed(self) -> bool:
        if str(self.status or "").strip().lower() == "repaid":
            return False
        if float(self.outstanding_balance or 0.0) <= 0.0:
            return False
        return not self.is_overdue

    @property
    def manual_repayment_message(self) -> str:
        if str(self.status or "").strip().lower() == "repaid" or float(self.outstanding_balance or 0.0) <= 0.0:
            return "This loan is already cleared. No manual repayment is needed."
        if self.is_overdue:
            return (
                "Manual repayment is locked because this loan is overdue. "
                "Add money to your wallet and automatic deductions will continue until the balance is cleared."
            )
        return (
            "Manual repayment is available while this loan stays on schedule. "
            "Users and agents can make part-payments or clear the full balance here."
        )
