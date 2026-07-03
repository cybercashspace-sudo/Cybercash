from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    
    # User who triggered the action
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Action type (e.g., "WALLET_DEBIT", "WALLET_CREDIT", "TRANSFER_SENT", "TRANSFER_RECEIVED", "TOPUP", "DELETE_USER")
    action = Column(String, nullable=False, index=True)
    
    # Related transaction ID (if applicable)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)
    
    # Resource type affected (e.g., "wallet", "user", "transaction")
    resource_type = Column(String, nullable=True)
    
    # Resource ID (e.g., wallet.id, user.id)
    resource_id = Column(Integer, nullable=True)
    
    # Balance information for reconciliation
    before_balance = Column(Numeric(20, 2), nullable=True)  # Wallet balance before action
    after_balance = Column(Numeric(20, 2), nullable=True)   # Wallet balance after action
    amount_changed = Column(Numeric(20, 2), nullable=True)  # +/- amount in this transaction
    
    # Security metadata
    ip_address = Column(String, nullable=True)
    device_fingerprint = Column(String, nullable=True)
    device_id = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    
    # Detailed description
    description = Column(String, nullable=True)
    
    # Metadata for additional context (JSON stored as string)
    metadata_json = Column(String, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    transaction = relationship("Transaction", back_populates="audit_logs")
    wallet = relationship(
        "Wallet",
        back_populates="audit_logs",
        primaryjoin="and_(Wallet.id==foreign(AuditLog.resource_id), AuditLog.resource_type=='wallet')",
        viewonly=True,
    )
