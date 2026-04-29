from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.database import Base

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True) # If payment is agent-assisted

    processor = Column(String, nullable=False) # e.g., 'momo', 'paystack', 'bank'
    type = Column(String, nullable=False) # e.g., 'deposit', 'withdrawal', 'airtime_payment'
    amount = Column(Float, nullable=False)
    currency = Column(String, default="GHS")
    
    status = Column(String, default="pending") # e.g., 'pending', 'successful', 'failed', 'reversed'
    
    processor_transaction_id = Column(String, nullable=True, unique=True) # ID from the payment processor
    our_transaction_id = Column(String, nullable=True, unique=True) # Our internal reference ID

    metadata_json = Column(String, nullable=True) # JSON field for storing additional processor-specific data

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="payments")
    agent = relationship("Agent", back_populates="payments") # Assuming agent can initiate payments
    journal_entries = relationship("JournalEntry", back_populates="payments")
