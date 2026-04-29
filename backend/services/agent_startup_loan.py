from __future__ import annotations

import json
from typing import Final

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Agent, Transaction


STARTUP_LOAN_CREDIT_TX_TYPE: Final[str] = "agent_startup_loan_credit"
STARTUP_LOAN_USAGE_TX_TYPES: Final[tuple[str, str]] = (
    "agent_airtime_sale",
    "agent_data_bundle_sale",
)


async def get_locked_startup_loan_balance(db: AsyncSession, agent_id: int) -> float:
    credit_query = await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0.0)).filter(
            Transaction.agent_id == agent_id,
            Transaction.type == STARTUP_LOAN_CREDIT_TX_TYPE,
            Transaction.status == "completed",
        )
    )
    startup_credit_total = float(credit_query.scalar_one() or 0.0)

    usage_query = await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0.0)).filter(
            Transaction.agent_id == agent_id,
            Transaction.type.in_(STARTUP_LOAN_USAGE_TX_TYPES),
            Transaction.status == "completed",
        )
    )
    startup_usage_total = float(usage_query.scalar_one() or 0.0)

    return max(0.0, startup_credit_total - startup_usage_total)


async def get_withdrawable_agent_float(db: AsyncSession, agent: Agent) -> float:
    locked_startup_balance = await get_locked_startup_loan_balance(db, agent.id)
    return max(0.0, float(agent.float_balance or 0.0) - locked_startup_balance)


async def grant_startup_loan_credit(
    db: AsyncSession,
    *,
    user_id: int,
    wallet_id: int,
    agent: Agent,
    amount: float,
    currency: str = "GHS",
) -> bool:
    amount = float(amount or 0.0)
    if amount <= 0:
        return False

    existing_result = await db.execute(
        select(Transaction).filter(
            Transaction.agent_id == agent.id,
            Transaction.type == STARTUP_LOAN_CREDIT_TX_TYPE,
            Transaction.status == "completed",
        )
    )
    if existing_result.scalars().first():
        return False

    agent.float_balance = float(agent.float_balance or 0.0) + amount
    db.add(agent)

    db.add(
        Transaction(
            user_id=user_id,
            wallet_id=wallet_id,
            agent_id=agent.id,
            type=STARTUP_LOAN_CREDIT_TX_TYPE,
            amount=amount,
            currency=currency,
            status="completed",
            metadata_json=json.dumps(
                {
                    "purpose": "agent_startup_loan",
                    "non_withdrawable": True,
                    "allowed_uses": list(STARTUP_LOAN_USAGE_TX_TYPES),
                }
            ),
        )
    )
    return True
