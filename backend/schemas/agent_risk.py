from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class AgentRiskProfileBase(BaseModel):
    agent_id: int
    credit_score: int
    risk_level: str
    recommended_limit: float

class AgentRiskProfileCreate(AgentRiskProfileBase):
    pass

class AgentRiskProfileInDB(AgentRiskProfileBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    last_calculated: datetime

class RiskEventBase(BaseModel):
    agent_id: int
    event_type: str
    severity: str
    description: Optional[str] = None

class RiskEventCreate(RiskEventBase):
    pass

class RiskEventInDB(RiskEventBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    timestamp: datetime
