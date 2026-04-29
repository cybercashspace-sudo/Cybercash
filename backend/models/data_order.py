import uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.sql import func

from backend.database import Base


class DataOrder(Base):
    __tablename__ = "data_orders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True, index=True)
    bundle_catalog_id = Column(Integer, ForeignKey("bundle_catalog.id"), nullable=True, index=True)

    network = Column(String(20), nullable=False)
    phone = Column(String(15), nullable=False)
    bundle_id = Column(Integer, nullable=False)

    amount = Column(Float, nullable=False, default=0.0)
    currency = Column(String(10), nullable=False, default="GHS")

    status = Column(String(20), nullable=False, default="pending")
    provider = Column(String(20), nullable=False, default="idata")
    provider_reference = Column(String, nullable=True, index=True)
    provider_response_json = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

