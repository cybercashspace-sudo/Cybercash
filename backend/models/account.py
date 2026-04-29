from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.database import Base

class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False) # e.g., "Cash in Bank", "Customer Wallets", "Agent Float"
    type = Column(String, nullable=False) # e.g., "Asset", "Liability", "Equity", "Revenue", "Expense"
    description = Column(String, nullable=True)
    
    # Current balance of this account (can be dynamically calculated from ledger entries)
    # For simplicity, we'll store it and update it upon ledger entry creation.
    balance = Column(Float, default=0.0) 

    parent_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    parent_account = relationship("Account", remote_side=[id], back_populates="child_accounts")
    child_accounts = relationship("Account", back_populates="parent_account")
    ledger_entries = relationship("LedgerEntry", back_populates="account")
