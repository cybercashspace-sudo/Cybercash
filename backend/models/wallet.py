
from sqlalchemy import Column, Integer, Float, ForeignKey, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database import Base

class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    currency = Column(String, default="GHS")
    balance = Column(Float, default=0.0) # Available Balance
    escrow_balance = Column(Float, default=0.0)
    loan_balance = Column(Float, default=0.0) # Could represent funds in a loan sub-account or outstanding debt
    investment_balance = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_frozen = Column(Boolean, default=False) # New field for admin control to freeze wallet
    metadata_json = Column(String, nullable=True) # For any additional wallet-specific data

    transactions = relationship("Transaction", back_populates="wallet")
