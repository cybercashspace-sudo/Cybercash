from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.models import User, Agent, Transaction, Wallet
from backend.schemas.agent import AgentCreate
from backend.core.config import settings
from fastapi import HTTPException, status, Depends
from backend.database import get_db
from backend.services.settings_service import get_or_create_platform_settings

class AgentService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_agent(self, user_id: int, initial_status: str = "pending") -> Agent:
        # Check if an agent record already exists for this user
        result = await self.db.execute(select(Agent).filter(Agent.user_id == user_id))
        existing_agent = result.scalars().first()
        if existing_agent:
            # If agent already exists and is active, raise an error
            if existing_agent.status == "active":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is already an active agent.")
            # If agent exists but is pending/suspended, we might want to update or re-initiate
            # For simplicity, we'll return the existing one if not active, to be updated later.
            return existing_agent

        platform_settings = await get_or_create_platform_settings(self.db)
        agent = Agent(
            user_id=user_id,
            status=initial_status,
            commission_rate=float(platform_settings.commission_rate or settings.AGENT_COMMISSION_RATE),
            float_balance=0.0
        )
        self.db.add(agent)
        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def activate_agent(self, agent: Agent) -> Agent:
        agent.status = "active"
        result = await self.db.execute(select(User).filter(User.id == agent.user_id))
        user = result.scalars().first()
        if user:
            user.is_agent = True # Mark the user as an agent
            self.db.add(user)
        self.db.add(agent)
        await self.db.commit()
        await self.db.refresh(agent)
        if user:
            await self.db.refresh(user)
        return agent

async def get_agent_service(db: AsyncSession = Depends(get_db)) -> AgentService:
    return AgentService(db)
