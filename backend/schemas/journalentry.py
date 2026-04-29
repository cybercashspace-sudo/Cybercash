from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime

# Forward declaration for LedgerEntryResponse
class LedgerEntryResponse(BaseModel):
    id: int
    account_id: int
    debit: float
    credit: float
    description: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class JournalEntryBase(BaseModel):
    transaction_id: Optional[int] = None
    payment_id: Optional[int] = None
    crypto_transaction_id: Optional[int] = None
    description: str

class JournalEntryCreate(JournalEntryBase):
    # When creating a JournalEntry, we might also provide the ledger entries directly
    ledger_entries: List["LedgerEntryCreate"]

class JournalEntryResponse(JournalEntryBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    ledger_entries: List[LedgerEntryResponse]

class LedgerEntryCreate(BaseModel):
    account_id: int
    debit: float = 0.0
    credit: float = 0.0
    description: Optional[str] = None
