from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
from decimal import Decimal
import random
import hashlib # For CVV hashing
import uuid
from typing import List # Added import

from .. import models, schemas
from ..core.config import settings
from ..services.ledger_service import LedgerService # For ledger entries
from ..services.transaction_engine import TransactionEngine, get_transaction_engine # New Import
from fastapi import HTTPException, status, Depends
from ..database import get_db # New Import
from ..services.ledger_service import get_ledger_service # New Import
from ..schemas.virtual_card import VirtualCardCreate, VirtualCardLoadFunds, VirtualCardUpdateLimit # Added import
from ..core.transaction_types import TransactionType

class VirtualCardService:
    def __init__(self, db: AsyncSession, ledger_service: LedgerService, transaction_engine: TransactionEngine):
        self.db = db
        self.ledger_service = ledger_service
        self.transaction_engine = transaction_engine

    def _generate_card_details(self):
        """
        Simulates generation of card number, expiry, and CVV.
        In a real system, this would come from a card issuer API.
        """
        card_number = ''.join([str(random.randint(0, 9)) for _ in range(16)])
        expiry_month = str(random.randint(1, 12)).zfill(2)
        expiry_year = str(datetime.now().year + random.randint(3, 5))[-2:] # 3-5 years from now
        expiry_date = f"{expiry_month}/{expiry_year}"
        cvv = ''.join([str(random.randint(0, 9)) for _ in range(3)])
        return card_number, expiry_date, cvv

    @staticmethod
    def _normalize_card_status(status_value: str | None) -> str:
        status = str(status_value or "").strip().lower()
        if status == "frozen":
            return "blocked"
        return status

    async def get_primary_virtual_card(self, user_id: int) -> models.VirtualCard | None:
        """
        Return the most relevant card for the user.

        We prefer active/blocked cards so the screen always shows the live card.
        If the account only has historical rows, fall back to the newest card.
        """
        result = await self.db.execute(
            select(models.VirtualCard)
            .filter(models.VirtualCard.user_id == user_id)
            .order_by(models.VirtualCard.created_at.desc(), models.VirtualCard.id.desc())
        )
        cards = list(result.scalars().all())
        if not cards:
            return None

        for card in cards:
            if self._normalize_card_status(card.status) in {"active", "blocked"}:
                return card

        return cards[0]

    async def request_virtual_card(
        self,
        user_id: int,
        card_request: VirtualCardCreate
    ) -> models.VirtualCard:
        # Idempotent issuance: if the user already has a live card, reuse it
        # instead of charging another issuance fee or creating a duplicate row.
        existing_card = await self.get_primary_virtual_card(user_id)
        if existing_card:
            return existing_card

        result = await self.db.execute(select(models.User).filter(models.User.id == user_id))
        user = result.scalars().first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        result = await self.db.execute(select(models.Wallet).filter(models.Wallet.user_id == user_id))
        user_wallet = result.scalars().first()
        if not user_wallet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User does not have a primary wallet")

        issuance_fee = Decimal(str(settings.VIRTUAL_CARD_CREATION_FEE_GHS))
        wallet_balance = Decimal(str(user_wallet.balance or 0.0))

        if wallet_balance < issuance_fee:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient balance. GHS {float(issuance_fee):,.2f} is required to create a new virtual card.",
            )
        
        # Deduct issuance fee
        user_wallet.balance = wallet_balance - issuance_fee
        
        card_number, expiry_date, cvv = self._generate_card_details()
        cvv_hashed = hashlib.sha256(cvv.encode()).hexdigest()

        # Create virtual card
        virtual_card = models.VirtualCard(
            user_id=user_id,
            card_number=card_number,
            expiry_date=expiry_date,
            cvv_hashed=cvv_hashed,
            currency=card_request.currency,
            balance=0.0, # Cards are issued with 0 balance initially
            spending_limit=card_request.spending_limit,
            status="active",
            type=card_request.type,
            issuance_fee_paid=issuance_fee
        )
        self.db.add(virtual_card)
        await self.db.flush() # Flush to get card ID for transaction metadata

        # Record fee transaction
        fee_transaction = models.Transaction(
            user_id=user_id,
            wallet_id=user_wallet.id,
            type=TransactionType.VIRTUAL_CARD_ISSUANCE_FEE,
            entry_type="debit",
            amount=float(issuance_fee),
            currency="GHS",
            status="completed",
            metadata_json=(
                f'{{"virtual_card_id": {virtual_card.id}, '
                f'"card_type": "{card_request.type}", '
                f'"creation_fee_ghs": {float(issuance_fee)}}}'
            ),
        )
        self.db.add(fee_transaction)
        await self.db.flush()

        # Create ledger entries for fee
        await self.ledger_service.create_journal_entry(
                description=f"Virtual Card Issuance Fee for User {user_id}",
                ledger_entries_data=[
                    {"account_name": "Customer Wallets (Liability)", "debit": float(issuance_fee), "credit": 0.0},
                    {"account_name": "Revenue - Card Usage Share", "debit": 0.0, "credit": float(issuance_fee)} # Adjusted account name
                ],
                transaction=fee_transaction
        )

        await self.db.commit()
        await self.db.refresh(user_wallet)
        await self.db.refresh(virtual_card)
        return virtual_card

    async def load_virtual_card_funds(
        self,
        user_id: int,
        card_id: int,
        load_request: VirtualCardLoadFunds
    ) -> models.VirtualCard:
        # Verify card ownership first (Engine handles wallet, but we need card check)
        result = await self.db.execute(select(models.VirtualCard).filter(
            models.VirtualCard.id == card_id,
            models.VirtualCard.user_id == user_id
        ))
        virtual_card = result.scalars().first()
        if not virtual_card:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Virtual card not found or does not belong to user")

        if self._normalize_card_status(virtual_card.status) != "active":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Card must be active before it can be loaded.")

        if virtual_card.type == "one-time" and virtual_card.balance > 0:
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One-time cards cannot be reloaded after initial funding")

        # Use Unified Transaction Engine
        try:
            await self.transaction_engine.process_transaction(
                user_id=user_id,
                transaction_type="VIRTUAL_CARD_LOAD",
                amount=load_request.amount,
                metadata={"card_id": card_id}
            )
        except ValueError as e:
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        # Refresh card to get updated balance
        await self.db.refresh(virtual_card)
        return virtual_card

    async def update_virtual_card_spending_limit(
        self,
        user_id: int,
        card_id: int,
        limit_request: VirtualCardUpdateLimit
    ) -> models.VirtualCard:
        result = await self.db.execute(select(models.VirtualCard).filter(
            models.VirtualCard.id == card_id,
            models.VirtualCard.user_id == user_id
        ))
        virtual_card = result.scalars().first()
        if not virtual_card:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Virtual card not found or does not belong to user")

        virtual_card.spending_limit = limit_request.spending_limit
        await self.db.commit()
        await self.db.refresh(virtual_card)
        return virtual_card

    async def update_virtual_card_status(
        self,
        user_id: int,
        card_id: int,
        status_value: str
    ) -> models.VirtualCard:
        result = await self.db.execute(select(models.VirtualCard).filter(
            models.VirtualCard.id == card_id,
            models.VirtualCard.user_id == user_id
        ))
        virtual_card = result.scalars().first()
        if not virtual_card:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Virtual card not found or does not belong to user")

        normalized_status = self._normalize_card_status(status_value)
        if normalized_status not in {"active", "blocked"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid virtual card status.")

        virtual_card.status = normalized_status
        await self.db.commit()
        await self.db.refresh(virtual_card)
        return virtual_card

    async def get_user_virtual_cards(self, user_id: int) -> List[models.VirtualCard]:
        result = await self.db.execute(
            select(models.VirtualCard)
            .filter(models.VirtualCard.user_id == user_id)
            .order_by(models.VirtualCard.created_at.desc(), models.VirtualCard.id.desc())
        )
        return result.scalars().all()

    async def get_virtual_card_details(self, user_id: int, card_id: int) -> models.VirtualCard:
        result = await self.db.execute(select(models.VirtualCard).filter(
            models.VirtualCard.id == card_id,
            models.VirtualCard.user_id == user_id
        ))
        virtual_card = result.scalars().first()
        if not virtual_card:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Virtual card not found or does not belong to user")
        return virtual_card

    async def replace_virtual_card(self, user_id: int, card_id: int) -> models.VirtualCard:
        """
        Reissue the existing card in place so the account keeps a single live card row.
        """
        result = await self.db.execute(
            select(models.VirtualCard).filter(
                models.VirtualCard.id == card_id,
                models.VirtualCard.user_id == user_id
            )
        )
        virtual_card = result.scalars().first()
        if not virtual_card:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Virtual card not found or does not belong to user")

        card_number, expiry_date, cvv = self._generate_card_details()
        virtual_card.card_number = card_number
        virtual_card.expiry_date = expiry_date
        virtual_card.cvv_hashed = hashlib.sha256(cvv.encode()).hexdigest()
        virtual_card.provider_card_id = f"reissue-{uuid.uuid4().hex[:24]}"
        virtual_card.status = "active"

        await self.db.commit()
        await self.db.refresh(virtual_card)
        return virtual_card

# Dependency
async def get_virtual_card_service(
    db: AsyncSession = Depends(get_db), 
    ledger_service: LedgerService = Depends(get_ledger_service),
    transaction_engine: TransactionEngine = Depends(get_transaction_engine)
) -> VirtualCardService:
    return VirtualCardService(db, ledger_service, transaction_engine)
