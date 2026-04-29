import json
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Commission, Transaction


async def record_commission(
    db: AsyncSession,
    *,
    agent_id: int,
    amount: float,
    currency: str = "GHS",
    commission_type: str = "AGENT_TRANSACTION",
    status: str = "accrued",
    transaction: Optional[Transaction] = None,
    user_id: Optional[int] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> Optional[Commission]:
    if amount == 0:
        return None

    row = Commission(
        agent_id=agent_id,
        transaction_id=transaction.id if transaction else None,
        user_id=user_id,
        amount=amount,
        currency=currency,
        commission_type=commission_type,
        status=status,
        metadata_json=json.dumps(metadata or {}),
    )
    db.add(row)
    await db.flush()
    return row
