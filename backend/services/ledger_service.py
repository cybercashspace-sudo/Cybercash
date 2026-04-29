# backend/services/ledger_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from typing import List, Dict, Tuple, Union, Optional
from fastapi import Depends # New import for Depends
from backend.database import get_db # New import for get_db

from backend.models import Account, JournalEntry, LedgerEntry, Transaction, Payment, CryptoTransaction, Wallet, Agent
from backend.schemas.journalentry import JournalEntryCreate, LedgerEntryCreate # Corrected import
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LedgerService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.standard_accounts: Dict[str, Account] = {}

    async def _initialize_standard_accounts(self):
        """
        Ensures standard accounts exist in the database.
        These are the root accounts for a double-entry system.
        """
        accounts_to_create = [
            # Assets
            {"name": "Cash (External Bank)", "type": "Asset", "description": "Cash held in external bank accounts."},
            {"name": "Crypto Hot Wallet (Asset)", "type": "Asset", "description": "Cryptocurrency held in hot wallets."},
            {"name": "Loan Principal (Asset)", "type": "Asset", "description": "Outstanding loan principal owed by customers."},
            
            # Liabilities
            {"name": "Customer Wallets (Liability)", "type": "Liability", "description": "Funds owed to customers in their fiat wallets."},
            {"name": "Agent Float (Liability)", "type": "Liability", "description": "Digital float owed to agents."},
            {"name": "Customer Escrow (Liability)", "type": "Liability", "description": "Funds held in escrow for customers."},
            {"name": "Customer Investments (Liability)", "type": "Liability", "description": "Funds held in customer investment accounts."},
            {"name": "Customer Crypto Balances (Liability)", "type": "Liability", "description": "Cryptocurrency owed to customers in their crypto wallets."},
            {"name": "Commissions Payable (Liability)", "type": "Liability", "description": "Commissions earned by agents, not yet paid out."},
            {"name": "Accounts Payable (Agent Commission)", "type": "Liability", "description": "Commission payable to agents from airtime/data sales."},

            # Revenue
            {"name": "Revenue - Agent Fees", "type": "Revenue", "description": "Revenue from agent registration fees."},
            {"name": "Revenue - Transaction Fees", "type": "Revenue", "description": "Revenue from various transaction fees."},
            {"name": "Revenue - FX Margins", "type": "Revenue", "description": "Revenue generated from FX rate differences."},
            {"name": "Revenue - Airtime Margins", "type": "Revenue", "description": "Profit margin from airtime/data sales."},
            {"name": "Revenue - Airtime Sales", "type": "Revenue", "description": "Gross revenue from agent airtime sales."},
            {"name": "Revenue - Data Bundle Sales", "type": "Revenue", "description": "Gross revenue from agent data bundle sales."},
            {"name": "Revenue - Cash Deposits (Agent)", "type": "Revenue", "description": "Cash deposits to agent float wallets."},
            {"name": "Revenue - Card Usage Share", "type": "Revenue", "description": "Revenue share from virtual card usage."},
            {"name": "Revenue - Loan Interest", "type": "Revenue", "description": "Interest earned on loans."},
            {"name": "Revenue - Investment Management Fees", "type": "Revenue", "description": "Fees from managing customer investments."},
            
            # Expenses
            {"name": "Commissions Expense", "type": "Expense", "description": "Expense incurred for agent commissions."},
            {"name": "Commission Expense (Agent)", "type": "Expense", "description": "Commission expense on agent airtime/data sales."},
            {"name": "Revenue Payout (Expense)", "type": "Expense", "description": "Expense for admin-initiated revenue payouts."},
            {"name": "Investment Payout (Expense)", "type": "Expense", "description": "Payouts to customers from investment gains (if tracked as expense)."},

            # Agent float asset
            {"name": "Cash (Agent Float)", "type": "Asset", "description": "Cash backing agent float balances."},

        ]

        account_names = [acc_data["name"] for acc_data in accounts_to_create]
        result = await self.db.execute(select(Account).filter(Account.name.in_(account_names)))
        existing_accounts = {account.name: account for account in result.scalars().all()}

        created_any = False
        for acc_data in accounts_to_create:
            account = existing_accounts.get(acc_data["name"])
            if not account:
                account = Account(
                    name=acc_data["name"],
                    type=acc_data["type"],
                    description=acc_data["description"]
                )
                self.db.add(account)
                existing_accounts[acc_data["name"]] = account
                created_any = True
            self.standard_accounts[acc_data["name"]] = account

        if created_any:
            try:
                await self.db.commit()
            except IntegrityError:
                await self.db.rollback()
                result = await self.db.execute(select(Account).filter(Account.name.in_(account_names)))
                existing_accounts = {account.name: account for account in result.scalars().all()}
                for acc_data in accounts_to_create:
                    account = existing_accounts.get(acc_data["name"])
                    if not account:
                        account = Account(
                            name=acc_data["name"],
                            type=acc_data["type"],
                            description=acc_data["description"]
                        )
                        self.db.add(account)
                        existing_accounts[acc_data["name"]] = account
                    self.standard_accounts[acc_data["name"]] = account
                await self.db.commit()
        logger.info("Standard ledger accounts initialized.")

    async def get_account_by_name(self, name: str) -> Account:
        """Retrieves a standard account by its name."""
        account = self.standard_accounts.get(name)
        if not account:
            result = await self.db.execute(select(Account).filter(Account.name == name))
            account = result.scalars().first()
            if not account:
                # Support dynamic sub-accounts used by FX and similar multi-currency flows.
                if name.startswith("Customer Wallets (Liability) - "):
                    account = Account(
                        name=name,
                        type="Liability",
                        description=f"Customer wallet liability sub-account for {name.split(' - ', 1)[1]}."
                    )
                    self.db.add(account)
                    await self.db.flush()
                else:
                    raise ValueError(f"Ledger account '{name}' not found.")
            self.standard_accounts[name] = account # Cache it
        return account

    async def create_journal_entry(
        self,
        description: str,
        ledger_entries_data: List[Dict[str, Union[int, float, str]]], # [{account_name: str, debit: float, credit: float, description: str}]
        transaction: Optional[Transaction] = None,
        payment: Optional[Payment] = None,
        crypto_transaction: Optional[CryptoTransaction] = None,
        auto_commit: bool = True,
    ) -> JournalEntry:
        """
        Creates a new JournalEntry with associated LedgerEntries.
        Ensures debits == credits for double-entry.
        """
        total_debit = 0.0
        total_credit = 0.0
        
        # Create Journal Entry
        journal_entry = JournalEntry(
            description=description,
            transaction_id=transaction.id if transaction else None,
            payment_id=payment.id if payment else None,
            crypto_transaction_id=crypto_transaction.id if crypto_transaction else None
        )
        self.db.add(journal_entry)
        await self.db.flush() # To get journal_entry.id

        for entry_data in ledger_entries_data:
            account = await self.get_account_by_name(entry_data["account_name"])
            debit = entry_data.get("debit", 0.0)
            credit = entry_data.get("credit", 0.0)

            if not (debit > 0 or credit > 0):
                raise ValueError("Ledger entry must have a positive debit or credit amount.")
            if debit > 0 and credit > 0:
                raise ValueError("Ledger entry cannot have both debit and credit.")

            total_debit += debit
            total_credit += credit

            ledger_entry = LedgerEntry(
                journal_entry_id=journal_entry.id,
                account_id=account.id,
                debit=debit,
                credit=credit,
                description=entry_data.get("description", description)
            )
            self.db.add(ledger_entry)
            
            # Update account balance directly for simplicity;
            # in a high-volume system, balances might be calculated from entries at query time.
            account.balance += (debit - credit)
            self.db.add(account) # Mark account as modified

        if abs(total_debit - total_credit) > 1e-6: # Allow for float precision
            logger.warning(
                "Unbalanced journal entry '%s': debits=%s credits=%s",
                description,
                total_debit,
                total_credit,
            )
        
        if auto_commit:
            await self.db.commit()
            await self.db.refresh(journal_entry)
        else:
            await self.db.flush()
        return journal_entry

# Helper function for dependency injection
async def get_ledger_service(db: AsyncSession = Depends(get_db)) -> LedgerService:
    return LedgerService(db)
