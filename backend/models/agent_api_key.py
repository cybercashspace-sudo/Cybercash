from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from backend.database import Base


class AgentAPIKey(Base):
    __tablename__ = "agent_api_keys"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(60), nullable=False)
    mode = Column(String(8), nullable=False, default="live", server_default="live")
    public_key = Column(String(40), nullable=False, unique=True, index=True)
    key_prefix = Column(String(24), nullable=False)
    key_hash = Column(String(64), nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
