from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession # Changed from Session
from sqlalchemy import select
from sqlalchemy.orm import joinedload # Keep joinedload for eager loading
from typing import List

from backend.database import get_db
from backend.models import JournalEntry, LedgerEntry, Account, User # Added User import
from backend.schemas.journalentry import JournalEntryResponse
from backend.schemas.account import AccountResponse
from backend.services.ledger_service import LedgerService, get_ledger_service
from backend.dependencies.auth import get_current_user # Assuming only admin or authenticated users can view

router = APIRouter(prefix="/ledger", tags=["Ledger"])

@router.get("/journal_entries", response_model=List[JournalEntryResponse])
async def get_all_journal_entries(
    db: AsyncSession = Depends(get_db),
    # For now, allowing any authenticated user to view.
    # In a real system, this would likely be restricted to admin roles.
    current_user: User = Depends(get_current_user) 
):
    """
    Retrieve all journal entries with their associated ledger entries.
    """
    try:
        # Eagerly load ledger_entries and their associated accounts to prevent N+1 queries
        result = await db.execute(select(JournalEntry).options(
            joinedload(JournalEntry.ledger_entries).joinedload(LedgerEntry.account)
        ))
        journal_entries = result.unique().scalars().all()
        return journal_entries
    finally:
        await db.close()

@router.get("/accounts_balance", response_model=List[AccountResponse])
async def get_all_account_balances(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user) # Restricted to authenticated users
):
    """
    Retrieve the current balances of all ledger accounts.
    """
    try:
        result = await db.execute(select(Account))
        accounts = result.scalars().all()
        return accounts
    finally:
        await db.close()
