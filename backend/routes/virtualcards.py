from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import json

from backend.database import get_db
from backend.models import User, VirtualCard, Wallet, Transaction
from backend.dependencies.auth import get_current_user
from backend.schemas.virtual_card import (
    VirtualCardCreate,
    VirtualCardLoadFunds,
    VirtualCardUpdateLimit,
    VirtualCardStatusUpdate,
    VirtualCardInDB,
    CardProcessorAuthorizationRequest,
    CardProcessorAuthorizationResponse,
)
from backend.services.virtual_card_service import VirtualCardService, get_virtual_card_service # New Import
from backend.services.transaction_engine import TransactionEngine, get_transaction_engine
from backend.core.transaction_types import TransactionType, normalize_transaction_type
from backend.core.config import settings

router = APIRouter(prefix="/virtualcards", tags=["Virtual Cards"])

@router.post("/request", response_model=VirtualCardInDB, status_code=status.HTTP_201_CREATED)
async def request_virtual_card(
    card_request: VirtualCardCreate,
    db: AsyncSession = Depends(get_db), # Changed type hint
    current_user: User = Depends(get_current_user),
    virtual_card_service: VirtualCardService = Depends(get_virtual_card_service)
):
    """
    Request a new virtual card for the authenticated user.
    Issuance fee will be deducted from the user's primary wallet.
    """
    try:
        return await virtual_card_service.request_virtual_card(user_id=current_user.id, card_request=card_request)
    finally:
        await db.close()

@router.post("/{card_id}/load", response_model=VirtualCardInDB)
async def load_virtual_card(
    card_id: int,
    load_request: VirtualCardLoadFunds,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    virtual_card_service: VirtualCardService = Depends(get_virtual_card_service)
):
    """
    Load funds onto an existing virtual card from the user's primary wallet.
    """
    try:
        return await virtual_card_service.load_virtual_card_funds(user_id=current_user.id, card_id=card_id, load_request=load_request)
    finally:
        await db.close()

@router.put("/{card_id}/limit", response_model=VirtualCardInDB)
async def update_virtual_card_spending_limit(
    card_id: int,
    limit_request: VirtualCardUpdateLimit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    virtual_card_service: VirtualCardService = Depends(get_virtual_card_service)
):
    """
    Update the spending limit of an existing virtual card.
    """
    try:
        return await virtual_card_service.update_virtual_card_spending_limit(user_id=current_user.id, card_id=card_id, limit_request=limit_request)
    finally:
        await db.close()


@router.patch("/{card_id}/status", response_model=VirtualCardInDB)
async def update_virtual_card_status(
    card_id: int,
    status_request: VirtualCardStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    virtual_card_service: VirtualCardService = Depends(get_virtual_card_service)
):
    """
    Freeze/Unfreeze a virtual card by changing its status.
    """
    try:
        return await virtual_card_service.update_virtual_card_status(
            user_id=current_user.id,
            card_id=card_id,
            status_value=status_request.status
        )
    finally:
        await db.close()

@router.get("/me", response_model=List[VirtualCardInDB])
async def list_virtual_cards_for_user(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    virtual_card_service: VirtualCardService = Depends(get_virtual_card_service)
):
    """
    Retrieve all virtual cards for the current authenticated user.
    """
    try:
        return await virtual_card_service.get_user_virtual_cards(user_id=current_user.id)
    finally:
        await db.close()

@router.get("/{card_id}", response_model=VirtualCardInDB)
async def get_virtual_card_details(
    card_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    virtual_card_service: VirtualCardService = Depends(get_virtual_card_service)
):
    """
    Retrieve details of a specific virtual card for the current authenticated user.
    """
    try:
        return await virtual_card_service.get_virtual_card_details(user_id=current_user.id, card_id=card_id)
    finally:
        await db.close()


@router.get("/{card_id}/transactions", response_model=List[dict])
async def get_virtual_card_transactions(
    card_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve transaction history related to a specific virtual card.
    """
    try:
        result = await db.execute(select(VirtualCard).filter(
            VirtualCard.id == card_id,
            VirtualCard.user_id == current_user.id
        ))
        card = result.scalars().first()
        if not card:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Virtual card not found or does not belong to user")

        tx_result = await db.execute(
            select(Transaction)
            .filter(Transaction.user_id == current_user.id)
            .order_by(Transaction.timestamp.desc())
        )
        transactions = tx_result.scalars().all()

        filtered = []
        for tx in transactions:
            tx_type = normalize_transaction_type(str(tx.type or ""))
            if tx_type not in {"CARD_LOAD", "CARD_SPEND", "CARD_WITHDRAW", "VIRTUAL_CARD_ISSUANCE_FEE"}:
                continue

            metadata = {}
            if tx.metadata_json:
                try:
                    metadata = json.loads(tx.metadata_json)
                except Exception:
                    metadata = {}

            tx_card_id = metadata.get("card_id") or metadata.get("virtual_card_id")
            if tx_card_id is None:
                continue
            if str(tx_card_id) != str(card_id):
                continue

            filtered.append({
                "id": tx.id,
                "type": tx.type,
                "amount": tx.amount,
                "currency": tx.currency,
                "status": tx.status,
                "timestamp": tx.timestamp.isoformat() if tx.timestamp else None,
                "metadata_json": tx.metadata_json,
            })

        return filtered
    finally:
        await db.close()


@router.post("/processor/authorize", response_model=CardProcessorAuthorizationResponse, status_code=status.HTTP_200_OK)
async def authorize_virtual_card_spend(
    request: CardProcessorAuthorizationRequest,
    db: AsyncSession = Depends(get_db),
    transaction_engine: TransactionEngine = Depends(get_transaction_engine),
    x_card_processor_key: str | None = Header(default=None),
):
    try:
        if x_card_processor_key != settings.CARD_PROCESSOR_WEBHOOK_KEY:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid processor key.")

        if not request.provider_card_id and not request.card_number:
            return CardProcessorAuthorizationResponse(
                approved=False,
                status="denied",
                reason="provider_card_id or card_number is required.",
            )

        query = select(VirtualCard)
        if request.provider_card_id:
            query = query.filter(VirtualCard.provider_card_id == request.provider_card_id)
        else:
            query = query.filter(VirtualCard.card_number == request.card_number)

        result = await db.execute(query)
        card = result.scalars().first()
        if not card:
            return CardProcessorAuthorizationResponse(approved=False, status="denied", reason="Card not found.")

        if card.status.lower() != "active":
            return CardProcessorAuthorizationResponse(approved=False, status="denied", reason="Card is not active.")

        total_spend = request.amount + request.fee + request.fx_margin
        if card.spending_limit > 0 and total_spend > card.spending_limit:
            return CardProcessorAuthorizationResponse(
                approved=False,
                status="denied",
                reason="Card spending limit exceeded.",
            )

        wallet_result = await db.execute(select(Wallet).filter(Wallet.user_id == card.user_id))
        wallet = wallet_result.scalars().first()
        if not wallet:
            return CardProcessorAuthorizationResponse(approved=False, status="denied", reason="Wallet not found.")

        if wallet.balance < total_spend:
            return CardProcessorAuthorizationResponse(
                approved=False,
                status="denied",
                reason="Insufficient wallet balance.",
                wallet_balance_after=wallet.balance,
            )

        try:
            tx = await transaction_engine.process_transaction(
                user_id=card.user_id,
                transaction_type=TransactionType.CARD_SPEND,
                amount=request.amount,
                metadata={
                    "pin_verified": True,
                    "card_id": card.id,
                    "merchant_name": request.merchant_name,
                    "merchant_country": request.merchant_country,
                    "fee": request.fee,
                    "fx_margin": request.fx_margin,
                    "use_card_balance": False,
                    "channel": "CARD_NETWORK",
                    "provider_card_id": card.provider_card_id,
                    "processor_reference": request.processor_reference,
                },
            )
        except ValueError as exc:
            return CardProcessorAuthorizationResponse(approved=False, status="denied", reason=str(exc))

        await db.refresh(wallet)
        return CardProcessorAuthorizationResponse(
            approved=True,
            status="approved",
            transaction_id=tx.id,
            wallet_balance_after=wallet.balance,
        )
    finally:
        await db.close()
