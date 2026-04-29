
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship # Import relationship
from sqlalchemy.sql import func # Import func
from backend.database import Base

class VirtualCard(Base):
    __tablename__ = "virtualcards"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    card_number = Column(String, unique=True, nullable=False) # Ensure card numbers are unique
    expiry_date = Column(String, nullable=False) # MM/YY format
    cvv_hashed = Column(String, nullable=False) # Hashed CVV for simulated security
    currency = Column(String, default="USD") # Default to USD for Virtual Visa
    balance = Column(Float, default=0)
    spending_limit = Column(Float, default=0) # Max amount that can be spent with this card
    status = Column(String, default="active") # e.g., active, inactive, blocked
    type = Column(String, nullable=False, default="rechargeable") # "one-time" or "rechargeable"
    issuance_fee_paid = Column(Float, default=0) # Amount of issuance fee paid
    provider_card_id = Column(String, nullable=True, unique=True) # ID from the external card provider
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="virtual_cards") # Add relationship to User

