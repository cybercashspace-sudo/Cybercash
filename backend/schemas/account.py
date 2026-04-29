from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class AccountBase(BaseModel):
    name: str
    type: str # e.g., "Asset", "Liability", "Equity", "Revenue", "Expense"
    description: Optional[str] = None
    parent_account_id: Optional[int] = None

class AccountCreate(AccountBase):
    pass

class AccountResponse(AccountBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    balance: float # Current calculated balance
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Optional: nested child accounts or parent account info
    # child_accounts: List["AccountResponse"] = []
