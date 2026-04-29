from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.database import Base

class CryptoTransaction(Base):
    __tablename__ = "crypto_transactions"

    id = Column(Integer, primary_key=True, index=True)
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    crypto_wallet_id = Column(Integer, ForeignKey("crypto_wallets.id"), nullable=True)
    
    coin_type = Column(String, nullable=False) # e.g., "BTC", "USDT-TRC20"
    type = Column(String, nullable=False) # 'deposit' or 'withdrawal'
    amount = Column(Float, nullable=False)
    
    transaction_hash = Column(String, nullable=True, unique=True) # Blockchain transaction ID
    from_address = Column(String, nullable=True) # Sender address (for deposits)
    to_address = Column(String, nullable=True) # Receiver address (for withdrawals)
    
    fee = Column(Float, default=0.0) # Network fee for withdrawals

    status = Column(String, default="pending") # e.g., 'pending', 'confirmed', 'failed'
    metadata_json = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="crypto_transactions")
    crypto_wallet = relationship("CryptoWallet", back_populates="crypto_transactions")
    journal_entries = relationship("JournalEntry", back_populates="crypto_transactions")
