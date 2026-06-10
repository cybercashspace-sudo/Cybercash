
from sqlalchemy import
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database import Base

class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    currency = Column(String, default="GHS")
    balance = Column(Numeric(20, 2), nullable=False, default=0.0) # Available Balance
    escrow_balance = Column(Numeric(20, 2), nullable=False, default=0.0)
    loan_balance = Column(Numeric(20, 2), nullable=False, default=0.0)
    investment_balance = Column(Numeric(20, 2), nullable=False, default=0.0)
    version = Column(Integer, default=1, nullable=False) # Optimistic locking
    last_verified_at = Column(DateTime(timezone=True), nullable=True) # For audit reconciliation
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_frozen = Column(Boolean, default=False) # New field for admin control to freeze wallet
    is_deleted = Column(Boolean, default=False, index=True)  # Soft delete flag for data retention
    deleted_at = Column(DateTime(timezone=True), nullable=True)  # Timestamp when soft-deleted
    metadata_json = Column(String, nullable=True) # For any additional wallet-specific data

    transactions = relationship("Transaction", back_populates="wallet")
    audit_logs = relationship("AuditLog", back_populates="wallet", foreign_keys="[AuditLog.resource_id]", primaryjoin="and_(Wallet.id==AuditLog.resource_id, AuditLog.resource_type=='wallet')", viewonly=True)

    __table_args__ = (
        CheckConstraint('balance >= 0', name='check_balance_non_negative'),
        CheckConstraint('escrow_balance >= 0', name='check_escrow_non_negative'),
        CheckConstraint('investment_balance >= 0', name='check_investment_non_negative'),
    )
