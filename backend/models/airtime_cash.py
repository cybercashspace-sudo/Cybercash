import uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from backend.database import Base


class AirtimeCashSale(Base):
    __tablename__ = "airtime_cash_sales"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    phone = Column(String(20), nullable=False)
    network = Column(String(20), nullable=False)
    amount = Column(Float, nullable=False)
    payout_amount = Column(Float, nullable=False)
    payout_rate = Column(Float, nullable=False, default=0.8)
    currency = Column(String(10), default="GHS")

    status = Column(String(30), default="pending")
    merchant_number = Column(String(20), nullable=False)
    payout_provider = Column(String, nullable=True)
    provider_reference = Column(String, nullable=True)
    metadata_json = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    verified_at = Column(DateTime(timezone=True), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)


class AirtimeCashSmsLog(Base):
    __tablename__ = "airtime_cash_sms_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    sender = Column(String(20), nullable=True)
    message = Column(Text, nullable=False)
    received_at = Column(DateTime(timezone=True), server_default=func.now())

    parsed_sender = Column(String(20), nullable=True)
    parsed_amount = Column(Float, nullable=True)
    matched_sale_id = Column(String, ForeignKey("airtime_cash_sales.id"), nullable=True)
    metadata_json = Column(Text, nullable=True)
