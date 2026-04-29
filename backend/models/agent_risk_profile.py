from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database import Base

class AgentRiskProfile(Base):
    __tablename__ = "agent_risk_profiles"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), unique=True, index=True)
    
    credit_score = Column(Integer, default=0) # 0-100
    risk_level = Column(String, default="unknown") # e.g., "Very Safe", "Safe", "Medium", "Risky", "Dangerous"
    recommended_limit = Column(Float, default=0.0) # Max eligible loan amount
    last_calculated = Column(DateTime(timezone=True), server_default=func.now())

    agent = relationship("Agent", back_populates="risk_profile")
