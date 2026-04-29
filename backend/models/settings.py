from sqlalchemy import Column, Integer, Float, Boolean, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.database import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True, index=True)
    biometric = Column(Boolean, default=False, nullable=False)
    otp = Column(Boolean, default=True, nullable=False)
    auto_settle = Column(Boolean, default=True, nullable=False)
    sms_alerts = Column(Boolean, default=True, nullable=False)
    email_alerts = Column(Boolean, default=False, nullable=False)
    transaction_pin = Column(Boolean, default=True, nullable=False)
    device_binding = Column(Boolean, default=True, nullable=False)
    login_alerts = Column(Boolean, default=True, nullable=False)
    push_notifications = Column(Boolean, default=False, nullable=False)
    fraud_alerts = Column(Boolean, default=True, nullable=False)
    withdrawal_limit = Column(Float, default=2000.0, nullable=False)
    default_payout_method = Column(String, default="momo", nullable=False)
    preferred_currency = Column(String, default="GHS", nullable=False)
    fee_display = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="user_settings")


class PlatformSettings(Base):
    __tablename__ = "platform_settings"

    id = Column(Integer, primary_key=True, index=True)
    agent_registration_fee = Column(Float, default=100.0, nullable=False)
    platform_fee_percentage = Column(Float, default=0.01, nullable=False)
    withdrawal_limit = Column(Float, default=1000.0, nullable=False)
    fraud_threshold = Column(Float, default=1000.0, nullable=False)
    commission_rate = Column(Float, default=0.02, nullable=False)
    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    updated_by = relationship("User", foreign_keys=[updated_by_user_id])
