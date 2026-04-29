from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from backend.database import Base


class BundleCatalog(Base):
    __tablename__ = "bundle_catalog"
    __table_args__ = (
        UniqueConstraint("network", "bundle_code", name="uq_bundle_catalog_network_code"),
    )

    id = Column(Integer, primary_key=True, index=True)
    network = Column(String, nullable=False, index=True)
    bundle_code = Column(String, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String, nullable=False, default="GHS")
    provider = Column(String, nullable=False, default="momo")
    is_active = Column(Boolean, nullable=False, default=True)
    metadata_json = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
