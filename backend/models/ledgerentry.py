from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.database import Base

class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id = Column(Integer, primary_key=True, index=True)
    journal_entry_id = Column(Integer, ForeignKey("journal_entries.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    
    debit = Column(Float, default=0.0)
    credit = Column(Float, default=0.0)
    description = Column(String, nullable=True) # Specific description for this leg of the entry
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    journal_entry = relationship("JournalEntry", back_populates="ledger_entries")
    account = relationship("Account", back_populates="ledger_entries")
