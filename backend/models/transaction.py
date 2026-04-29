from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.database import Base

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True) # Optional, if not all transactions are agent-initiated
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False) # The user whose wallet is affected
    wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=False) # The specific wallet involved

    type = Column(String, nullable=False) # canonical type from backend.core.transaction_types
    amount = Column(Float, nullable=False)
    currency = Column(String, default="GHS") # Assuming Ghanaian Cedis based on previous context
    metadata_json = Column(String, nullable=True) # JSON metadata for provider/risk/reference fields
    
    commission_earned = Column(Float, default=0.0) # Commission for the agent on this transaction
    
    status = Column(String, default="pending") # e.g., 'pending', 'completed', 'failed', 'reversed'
    
    provider = Column(String, nullable=True) # e.g., 'paystack', 'momo'
    provider_reference = Column(String, nullable=True, unique=True) # Reference ID from the payment provider

    fx_rate = Column(Float, nullable=True) # Exchange rate applied for FX transactions
    fx_spread_amount = Column(Float, nullable=True) # Revenue earned from FX spread

    latitude = Column(Float, nullable=True) # Geo-location of the transaction
    longitude = Column(Float, nullable=True) # Geo-location of the transaction

    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    agent = relationship("Agent", back_populates="transactions")
    user = relationship("User", back_populates="transactions")
    wallet = relationship("Wallet", back_populates="transactions")
    journal_entries = relationship("JournalEntry", back_populates="transactions")
    commissions = relationship("Commission", back_populates="transaction")
