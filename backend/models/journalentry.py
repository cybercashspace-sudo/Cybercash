from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.database import Base

class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, index=True)
    
    # Optional links to originating transactions/payments
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)
    crypto_transaction_id = Column(Integer, ForeignKey("crypto_transactions.id"), nullable=True)

    description = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    transactions = relationship("Transaction", back_populates="journal_entries")
    payments = relationship("Payment", back_populates="journal_entries")
    crypto_transactions = relationship("CryptoTransaction", back_populates="journal_entries")

    ledger_entries = relationship("LedgerEntry", back_populates="journal_entry")
