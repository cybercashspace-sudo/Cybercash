from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.database import Base


class Commission(Base):
    __tablename__ = "commissions"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    amount = Column(Float, nullable=False)
    currency = Column(String, nullable=False, default="GHS")
    commission_type = Column(String, nullable=False, default="AGENT_TRANSACTION")
    status = Column(String, nullable=False, default="accrued")
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    agent = relationship("Agent", back_populates="commissions")
    transaction = relationship("Transaction", back_populates="commissions")
    user = relationship("User", back_populates="commissions")
