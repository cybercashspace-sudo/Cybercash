from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Float
from sqlalchemy.orm import relationship
from backend.database import Base
from werkzeug.security import generate_password_hash, check_password_hash

class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True)
    status = Column(String, default="pending")  # e.g., "pending", "active", "suspended"
    business_name = Column(String, nullable=True)
    ghana_card_id = Column(String, nullable=True, index=True)
    agent_location = Column(String, nullable=True)
    commission_rate = Column(Float, default=0.0) # Commission rate for the agent
    float_balance = Column(Float, default=0.0) # Agent's current cash float
    commission_balance = Column(Float, default=0.0) # Accumulated commissions
    pin_hash = Column(String, nullable=True) # Hashed 4-digit PIN for USSD access
    is_borrowing_frozen = Column(Boolean, default=False) # New field for admin control to freeze borrowing
    loan_auto_deduction_enabled = Column(Boolean, default=True)


    user = relationship("User", back_populates="agent")
    
    # Add relationship to transactions if agents initiate them
    transactions = relationship("Transaction", back_populates="agent")
    payments = relationship("Payment", back_populates="agent")
    loan_applications = relationship("LoanApplication", back_populates="agent")
    loans = relationship("Loan", back_populates="agent")
    risk_profile = relationship("AgentRiskProfile", back_populates="agent", uselist=False) # One-to-one
    risk_events = relationship("RiskEvent", back_populates="agent") # One-to-many
    commissions = relationship("Commission", back_populates="agent")

    def set_pin(self, pin: str):
        self.pin_hash = generate_password_hash(pin)

    def verify_pin(self, pin: str):
        return check_password_hash(self.pin_hash, pin)
