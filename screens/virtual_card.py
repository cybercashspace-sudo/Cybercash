import secrets
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.database import get_db
from backend.auth.dependencies import get_current_user
from backend.models import User, VirtualCard, Transaction
from backend.services.statement_service import StatementService
from backend.core.transaction_types import TransactionType

router = APIRouter(prefix="/api/virtual-card", tags=["Virtual Card"])

@router.get("/statement")
async def get_virtual_card_statement(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generates and returns a URL for the virtual card transaction statement."""
    
    # 1. Fetch user's virtual card
    card_query = await db.execute(
        select(VirtualCard).filter(VirtualCard.user_id == current_user.id)
    )
    card = card_query.scalars().first()
    if not card:
        raise HTTPException(status_code=404, detail="No virtual card found for this account.")

    # 2. Fetch recent card transactions (spends and loads)
    tx_query = await db.execute(
        select(Transaction).filter(
            Transaction.user_id == current_user.id,
            Transaction.type.in_([TransactionType.CARD_SPEND, TransactionType.CARD_LOAD])
        ).order_by(Transaction.timestamp.desc()).limit(100)
    )
    transactions = list(tx_query.scalars().all())

    # 3. Generate PDF via service
    statement_service = StatementService()
    try:
        pdf_url = statement_service.generate_pdf(current_user, card, transactions)
        return {"url": pdf_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate statement: {str(e)}")

@router.post("/replace")
async def replace_virtual_card(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Deactivates the current card and issues a new one with the transferred balance."""
    
    # 1. Fetch current active or frozen card
    card_query = await db.execute(
        select(VirtualCard).filter(
            VirtualCard.user_id == current_user.id,
            VirtualCard.status.in_(["active", "frozen"])
        )
    )
    old_card = card_query.scalars().first()
    
    balance_to_transfer = 0.0
    if old_card:
        balance_to_transfer = float(old_card.balance or 0.0)
        old_card.status = "replaced"
        old_card.balance = 0.0
        db.add(old_card)

    # 2. Issue new card details (In production, call your card provider API here)
    new_card = VirtualCard(
        user_id=current_user.id,
        card_number="4111" + "".join([str(secrets.randbelow(10)) for _ in range(12)]),
        cvv="".join([str(secrets.randbelow(10)) for _ in range(3)]),
        expiry="12/28",
        card_holder=current_user.full_name or "Cyber Cash User",
        balance=balance_to_transfer,
        status="active"
    )
    
    db.add(new_card)
    try:
        await db.commit()
        return {"message": "Card replaced successfully", "new_card_last4": new_card.card_number[-4:]}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Replacement failed: {str(e)}")