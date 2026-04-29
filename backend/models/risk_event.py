from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database import Base

class RiskEvent(Base):
    __tablename__ = "risk_events"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), index=True)
    
    event_type = Column(String, nullable=False) # e.g., "low_activity", "suspicious_transaction_spike", "late_repayment"
    severity = Column(String, default="medium") # e.g., "low", "medium", "high", "critical"
    description = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    agent = relationship("Agent", back_populates="risk_events")
