from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Float, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.database import Base

class CryptoWallet(Base):
    __tablename__ = "crypto_wallets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    coin_type = Column(String, nullable=False) # e.g., "BTC", "USDT-TRC20"
    address = Column(String, unique=True, nullable=False) # The unique deposit address for this user/coin
    
    # We might store a local balance for quick display, but the true balance is on the blockchain
    # This local balance would need to be updated via blockchain monitoring
    balance = Column(Float, default=0.0) 

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="crypto_wallets")
    crypto_transactions = relationship("CryptoTransaction", back_populates="crypto_wallet")
