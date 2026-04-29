from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from backend.database import Base


class AgentProfile(Base):
    __tablename__ = "agent_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True, nullable=False)
    ghana_card_number = Column(String, nullable=True, index=True)
    kyc_status = Column(String, default="pending")
    face_match_score = Column(Float, nullable=True)

    ghana_card_front_ref = Column(String, nullable=True)
    ghana_card_back_ref = Column(String, nullable=True)
    selfie_ref = Column(String, nullable=True)

    extracted_full_name = Column(String, nullable=True)
    extracted_dob = Column(String, nullable=True)
    extracted_expiry_date = Column(String, nullable=True)

    reviewed_by_admin_id = Column(Integer, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="agent_profile")

