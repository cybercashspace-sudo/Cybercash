from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.database import Base

class LoanApplication(Base):
    __tablename__ = "loan_applications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), index=True)
    
    amount = Column(Float, nullable=False)
    repayment_duration = Column(Integer, nullable=False) # requested duration in days or months
    purpose = Column(String, nullable=True) # e.g., "cash float", "airtime", "liquidity"
    
    # Loan Offer Details (generated after risk assessment)
    approved_amount = Column(Float, nullable=True)
    fee_percentage = Column(Float, nullable=True)
    offered_repayment_duration = Column(Integer, nullable=True) # in days or months
    
    status = Column(String, default="pending_admin_approval") # pending_admin_approval -> approved/rejected -> disbursed
    application_date = Column(DateTime(timezone=True), server_default=func.now())
    approved_date = Column(DateTime(timezone=True), nullable=True)
    rejected_date = Column(DateTime(timezone=True), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by_admin_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    review_note = Column(String, nullable=True)
    risk_score = Column(Integer, nullable=True) # Calculated by Risk Engine

    user = relationship("User", back_populates="loan_applications", foreign_keys=[user_id])
    agent = relationship("Agent", back_populates="loan_applications")
    loan = relationship("Loan", back_populates="application", uselist=False)
