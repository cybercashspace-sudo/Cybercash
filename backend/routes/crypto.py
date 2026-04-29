from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from datetime import datetime, timezone
import json
import uuid
from pydantic import BaseModel, Field
import requests

from backend.database import get_db
from backend.models import User, CryptoWallet, CryptoTransaction
from backend.schemas.cryptowallet import CryptoWalletCreate, CryptoWalletResponse # Corrected import
from backend.schemas.cryptotransaction import CryptoTransactionResponse # Corrected import
from backend.dependencies.auth import get_current_user
from backend.services.crypto import CryptoService
from backend.services.ledger_service import LedgerService, get_ledger_service
from backend.core.config import settings # New import # New import

router = APIRouter(
    prefix="/crypto",
    tags=["Crypto"]
)

crypto_service = CryptoService()

class CryptoWithdrawalRequest(BaseModel):
    to_address: str
    amount: float = Field(..., gt=0)
    coin_type: str

@router.get("/coins", response_model=List[str])
async def get_supported_coins():
    return crypto_service.get_supported_coins()


@router.get("/market/btc")
def get_btc_market_snapshot():
    btc_details = crypto_service.supported_coins.get("BTC", {})
    try:
        response = requests.get(
            "https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT",
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
        last_price = float(payload.get("lastPrice") or payload.get("price") or 0.0)
        price_change_percent = float(payload.get("priceChangePercent") or 0.0)
        high_price = float(payload.get("highPrice") or 0.0)
        low_price = float(payload.get("lowPrice") or 0.0)
        volume = float(payload.get("volume") or 0.0)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"BTC market data is temporarily unavailable: {exc}",
        )

    usd_to_ghs_rate = 12.0
    estimated_ghs_per_btc = last_price * usd_to_ghs_rate
    return {
        "symbol": "BTCUSDT",
        "network": btc_details.get("network", "Bitcoin"),
        "min_deposit_btc": float(btc_details.get("min_deposit", 0.0001) or 0.0001),
        "withdrawal_fee_btc": float(btc_details.get("withdrawal_fee", 0.00005) or 0.00005),
        "last_price_usdt": last_price,
        "price_change_percent_24h": price_change_percent,
        "high_price_usdt": high_price,
        "low_price_usdt": low_price,
        "volume_btc": volume,
        "usd_to_ghs_rate": usd_to_ghs_rate,
        "estimated_ghs_per_btc": estimated_ghs_per_btc,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": "binance",
    }

@router.post("/wallets", response_model=CryptoWalletResponse, status_code=status.HTTP_201_CREATED)
async def create_crypto_wallet(
    wallet_create: CryptoWalletCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        if not crypto_service.is_coin_supported(wallet_create.coin_type):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Coin type '{wallet_create.coin_type}' is not supported.")

        # Check if user already has a wallet for this coin type
        result = await db.execute(select(CryptoWallet).filter(
            CryptoWallet.user_id == current_user.id,
            CryptoWallet.coin_type == wallet_create.coin_type
        ))
        existing_wallet = result.scalars().first()
        if existing_wallet:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"User already has a {wallet_create.coin_type} wallet.")

        # Simulate address generation
        new_address = await crypto_service.generate_deposit_address(current_user.id, wallet_create.coin_type)

        db_wallet = CryptoWallet(
            user_id=current_user.id,
            coin_type=wallet_create.coin_type,
            address=new_address
        )
        db.add(db_wallet)
        await db.commit()
        await db.refresh(db_wallet)
        return db_wallet
    finally:
        await db.close()

@router.get("/wallets", response_model=List[CryptoWalletResponse])
async def list_crypto_wallets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        result = await db.execute(select(CryptoWallet).filter(CryptoWallet.user_id == current_user.id))
        return result.scalars().all()
    finally:
        await db.close()

@router.get("/wallets/{coin_type}/address", response_model=str)
async def get_deposit_address(
    coin_type: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        result = await db.execute(select(CryptoWallet).filter(
            CryptoWallet.user_id == current_user.id,
            CryptoWallet.coin_type == coin_type
        ))
        wallet = result.scalars().first()
        if not wallet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No {coin_type} wallet found for user. Please create one.")
        return wallet.address
    finally:
        await db.close()

@router.post("/withdraw", response_model=CryptoTransactionResponse, status_code=status.HTTP_202_ACCEPTED)
async def initiate_crypto_withdrawal(
    withdrawal_request: CryptoWithdrawalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_service: LedgerService = Depends(get_ledger_service) # Inject LedgerService
):
    try:
        # Get user's wallet for the coin type
        result = await db.execute(select(CryptoWallet).filter(
            CryptoWallet.user_id == current_user.id,
            CryptoWallet.coin_type == withdrawal_request.coin_type
        ))
        user_crypto_wallet = result.scalars().first()
        if not user_crypto_wallet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No {withdrawal_request.coin_type} wallet found for user.")
        
        # Check balance (using local balance for simulation)
        if user_crypto_wallet.balance < withdrawal_request.amount:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient crypto balance.")

        # Simulate network fee (this would come from crypto_service in real life)
        withdrawal_fee = crypto_service.supported_coins.get(withdrawal_request.coin_type, {}).get("withdrawal_fee", 0.0)
        
        if user_crypto_wallet.balance < (withdrawal_request.amount + withdrawal_fee):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Insufficient crypto balance to cover amount and fee ({withdrawal_fee}).")

        # Optimistically deduct from local balance
        user_crypto_wallet.balance -= (withdrawal_request.amount + withdrawal_fee)
        await db.flush() # Flush to update balance before transaction and ledger

        # Record pending crypto transaction
        db_crypto_transaction = CryptoTransaction(
            user_id=current_user.id,
            crypto_wallet_id=user_crypto_wallet.id,
            coin_type=withdrawal_request.coin_type,
            type="withdrawal",
            amount=withdrawal_request.amount,
            to_address=withdrawal_request.to_address,
            fee=withdrawal_fee,
            status="pending"
        )
        db.add(db_crypto_transaction)
        await db.flush() # Flush to get db_crypto_transaction.id for ledger

        # Create ledger entries for the optimistic deduction
        await ledger_service.create_journal_entry(
            description=f"Crypto Withdrawal Initiation by user {current_user.id} ({withdrawal_request.coin_type})",
            ledger_entries_data=[
                {"account_name": "Customer Crypto Balances (Liability)", "debit": (withdrawal_request.amount + withdrawal_fee), "credit": 0.0}, # User's crypto liability decreases
                {"account_name": "Crypto Hot Wallet (Asset)", "debit": 0.0, "credit": (withdrawal_request.amount + withdrawal_fee)} # Our crypto asset decreases
            ],
            crypto_transaction=db_crypto_transaction
        )

        # Broadcast transaction immediately and persist TX hash.
        crypto_response = await crypto_service.initiate_withdrawal(
            from_address="OUR_HOT_WALLET_ADDRESS", # Placeholder
            to_address=withdrawal_request.to_address,
            coin_type=withdrawal_request.coin_type,
            amount=withdrawal_request.amount
        )

        if crypto_response["status"] == "failed":
            # Revert balance, mark transaction failed
            user_crypto_wallet.balance += (withdrawal_request.amount + withdrawal_fee)
            db_crypto_transaction.status = "failed"

            # Create reversal ledger entry
            await ledger_service.create_journal_entry(
                description=f"Crypto Withdrawal Initiation Reversal for user {current_user.id} (failed)",
                ledger_entries_data=[
                    {"account_name": "Customer Crypto Balances (Liability)", "debit": 0.0, "credit": (withdrawal_request.amount + withdrawal_fee)}, # Revert liability decrease
                    {"account_name": "Crypto Hot Wallet (Asset)", "debit": (withdrawal_request.amount + withdrawal_fee), "credit": 0.0} # Revert crypto asset decrease
                ],
                crypto_transaction=db_crypto_transaction
            )
            await db.commit()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=crypto_response["message"])

        db_crypto_transaction.transaction_hash = crypto_response.get("transaction_hash")
        db_crypto_transaction.status = "awaiting_confirmation"
        await db.commit()
        await db.refresh(db_crypto_transaction)

        return db_crypto_transaction
    finally:
        await db.close()

@router.get("/transactions", response_model=List[CryptoTransactionResponse])
async def list_crypto_transactions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        result = await db.execute(select(CryptoTransaction).filter(CryptoTransaction.user_id == current_user.id))
        return result.scalars().all()
    finally:
        await db.close()

@router.post("/webhook/deposit")
async def crypto_deposit_webhook(
    payload: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    ledger_service: LedgerService = Depends(get_ledger_service) # Inject LedgerService
):
    try:
        # In a real system:
        # 1. Verify webhook signature/authenticity.
        # 2. Extract transaction details from payload.
        # 3. Prevent replay attacks.
        
        # Simulate processing the deposit notification
        processed_payload = await crypto_service.process_deposit_webhook(payload)

        if processed_payload["status"] == "error":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=processed_payload["message"])

        # Find the user's crypto wallet by deposit address
        deposit_address = payload.get("address")
        coin_type = payload.get("coin_type")
        amount = payload.get("amount")
        transaction_hash = payload.get("transaction_hash")
        confirmations = int(payload.get("confirmations", 0))

        if not all([deposit_address, coin_type, amount, transaction_hash]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing required fields in webhook payload.")

        result = await db.execute(select(CryptoWallet).filter(
            CryptoWallet.address == deposit_address,
            CryptoWallet.coin_type == coin_type
        ))
        crypto_wallet = result.scalars().first()

        if not crypto_wallet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crypto wallet not found for deposit address.")

        # Check for existing transaction hash to prevent duplicate credits
        result = await db.execute(select(CryptoTransaction).filter(
            CryptoTransaction.transaction_hash == transaction_hash,
            CryptoTransaction.type == "deposit"
        ))
        existing_tx = result.scalars().first()

        required_confirmations = settings.BTC_DEPOSIT_REQUIRED_CONFIRMATIONS if coin_type == "BTC" else 1
        if confirmations < required_confirmations:
            if not existing_tx:
                pending_tx = CryptoTransaction(
                    user_id=crypto_wallet.user_id,
                    crypto_wallet_id=crypto_wallet.id,
                    coin_type=coin_type,
                    type="deposit",
                    amount=amount,
                    from_address=payload.get("from_address"),
                    to_address=deposit_address,
                    transaction_hash=transaction_hash,
                    status="pending",
                    metadata_json=json.dumps({"confirmations": confirmations}),
                )
                db.add(pending_tx)
            else:
                existing_tx.status = "pending"
                existing_tx.metadata_json = json.dumps({"confirmations": confirmations})
                db.add(existing_tx)
            await db.commit()
            return {"message": f"Awaiting confirmations ({confirmations}/{required_confirmations})."}

        if existing_tx and existing_tx.status == "confirmed":
            return {"message": "Transaction already processed."}

        # Update local balance only once when confirmations threshold is met.
        crypto_wallet.balance += amount
        await db.flush()

        if existing_tx:
            existing_tx.status = "confirmed"
            existing_tx.metadata_json = json.dumps({"confirmations": confirmations})
            db_crypto_transaction = existing_tx
        else:
            db_crypto_transaction = CryptoTransaction(
                user_id=crypto_wallet.user_id,
                crypto_wallet_id=crypto_wallet.id,
                coin_type=coin_type,
                type="deposit",
                amount=amount,
                from_address=payload.get("from_address"),
                to_address=deposit_address,
                transaction_hash=transaction_hash,
                status="confirmed",
                metadata_json=json.dumps({"confirmations": confirmations}),
            )
            db.add(db_crypto_transaction)
            await db.flush()

        await ledger_service.create_journal_entry(
            description=f"Crypto Deposit by user {crypto_wallet.user_id} ({coin_type})",
            ledger_entries_data=[
                {"account_name": "Crypto Hot Wallet (Asset)", "debit": amount, "credit": 0.0},
                {"account_name": "Customer Crypto Balances (Liability)", "debit": 0.0, "credit": amount}
            ],
            crypto_transaction=db_crypto_transaction
        )
        await db.commit()

        return {"message": "Crypto deposit processed successfully."}
    finally:
        await db.close()
