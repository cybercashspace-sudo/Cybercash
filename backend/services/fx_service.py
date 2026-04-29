from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.database import get_db
from backend.models import User, Wallet, Transaction
from backend.services.ledger_service import LedgerService, get_ledger_service
from backend.core.config import settings
from fastapi import Depends, HTTPException, status
from typing import Tuple
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FxService:
    def __init__(self, db: AsyncSession, ledger_service: LedgerService):
        self.db = db
        self.ledger_service = ledger_service
        # For simplicity, using a fixed mock rate and spread.
        # In a real application, this would integrate with a real-time FX API.
        self.mock_rates = {
            "GHS": {"USD": 0.083, "EUR": 0.076, "GBP": 0.065, "GHS": 1.0},
            "USD": {"GHS": 12.0, "EUR": 0.92, "GBP": 0.78, "USD": 1.0},
            "EUR": {"GHS": 13.0, "USD": 1.08, "GBP": 0.85, "EUR": 1.0},
            "GBP": {"GHS": 15.5, "USD": 1.28, "EUR": 1.17, "GBP": 1.0}
        }
        self.fx_spread_percentage = settings.FX_SPREAD_PERCENTAGE # Define this in settings

    def get_exchange_rate(self, from_currency: str, to_currency: str) -> float:
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        if from_currency not in self.mock_rates or to_currency not in self.mock_rates[from_currency]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported currency exchange: {from_currency} to {to_currency}"
            )
        return self.mock_rates[from_currency][to_currency]

    def calculate_exchange(self, from_currency: str, to_currency: str, amount: float) -> Tuple[float, float, float]:
        """
        Calculates the amount received after exchange and the FX spread amount.
        Returns (amount_received, effective_rate, spread_amount).
        """
        base_rate = self.get_exchange_rate(from_currency, to_currency)
        
        # Apply spread. Assuming spread is applied to the 'buy' side for the customer
        # i.e., customer gets a slightly worse rate, and the difference is revenue.
        effective_rate = base_rate * (1 - self.fx_spread_percentage) # Customer gets less
        amount_received = amount * effective_rate
        
        # Calculate spread revenue
        # The amount if there was no spread: amount * base_rate
        # The amount customer actually receives: amount * effective_rate
        # Spread is the difference in amount_received
        spread_revenue = (amount * base_rate) - amount_received

        return amount_received, effective_rate, spread_revenue

    async def perform_exchange(self, user: User, from_currency: str, to_currency: str, amount: float) -> dict: # Changed return type hint
        if from_currency == to_currency:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot exchange to the same currency.")

        result = await self.db.execute(select(Wallet).filter(
            Wallet.user_id == user.id,
            Wallet.currency == from_currency
        ))
        from_wallet = result.scalars().first()

        result = await self.db.execute(select(Wallet).filter(
            Wallet.user_id == user.id,
            Wallet.currency == to_currency
        ))
        to_wallet = result.scalars().first()

        if not from_wallet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Wallet for {from_currency} not found.")
        if not to_wallet:
            # Create a new wallet for the target currency if it doesn't exist
            to_wallet = Wallet(user_id=user.id, currency=to_currency, balance=0.0)
            self.db.add(to_wallet)
            await self.db.flush() # Flush to get ID

        if from_wallet.balance < amount:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient funds in source wallet.")

        amount_received, effective_rate, spread_revenue = self.calculate_exchange(from_currency, to_currency, amount)
        
        # Update wallet balances
        from_wallet.balance -= amount
        to_wallet.balance += amount_received

        self.db.add(from_wallet)
        self.db.add(to_wallet)
        await self.db.flush()

        # Record transaction
        transaction = Transaction(
            user_id=user.id,
            wallet_id=from_wallet.id, # Link to the wallet from which funds were deducted
            type="fx_exchange",
            amount=-amount, # Negative for deduction from source
            currency=from_currency,
            status="completed",
            fx_rate=effective_rate,
            fx_spread_amount=spread_revenue,
            metadata_json=json.dumps({
                "to_currency": to_currency,
                "amount_received": amount_received,
                "original_amount": amount,
                "spread_percentage": self.fx_spread_percentage
            })
        )
        self.db.add(transaction)
        await self.db.flush()

        # Create ledger entries
        await self.ledger_service.create_journal_entry(
            description=f"FX Exchange: {amount} {from_currency} to {amount_received} {to_currency} for user {user.id}",
            ledger_entries_data=[
                # Debit customer's liability for from_currency
                {"account_name": f"Customer Wallets (Liability) - {from_currency}", "debit": amount, "credit": 0.0},
                # Credit customer's liability for to_currency
                {"account_name": f"Customer Wallets (Liability) - {to_currency}", "debit": 0.0, "credit": amount_received},
                # Credit FX Spread Revenue
                {"account_name": "Revenue - FX Margins", "debit": 0.0, "credit": spread_revenue}
            ],
            transaction=transaction
        )
        
        await self.db.commit()
        await self.db.refresh(from_wallet)
        await self.db.refresh(to_wallet)
        await self.db.refresh(transaction)
        
        # Return a dictionary with the required fields
        return {
            "transaction_id": transaction.id,
            "from_currency": from_currency,
            "to_currency": to_currency,
            "amount_sent": amount,
            "amount_received": amount_received,
            "exchange_rate": effective_rate,
            "spread_amount": spread_revenue,
            "message": "Currency exchange completed successfully."
        }

async def get_fx_service(db: AsyncSession = Depends(get_db), ledger_service: LedgerService = Depends(get_ledger_service)) -> FxService:
    return FxService(db, ledger_service)