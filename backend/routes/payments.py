from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
import json
from pydantic import BaseModel, Field

from backend.database import get_db
from backend.models import User, Wallet, Payment, Transaction
from backend.schemas.payment import PaymentResponse # Corrected import
from backend.dependencies.auth import get_current_user
from backend.services.momo import MomoService
from backend.services.ledger_service import LedgerService, get_ledger_service
from backend.services.transaction_engine import TransactionEngine, get_transaction_engine
from backend.core.config import settings
from backend.core.transaction_types import TransactionType

import uuid

router = APIRouter(
    prefix="/payments",
    tags=["Payments"]
)

momo_service = MomoService()

# Pydantic Schemas for Payment Initiation Requests
class MomoDepositInitiate(BaseModel):
    amount: float = Field(..., gt=0)
    currency: str = Field(default="GHS", min_length=3, max_length=10)
    phone_number: str

class MomoWithdrawalInitiate(BaseModel):
    amount: float = Field(..., gt=0)
    currency: str = Field(default="GHS", min_length=3, max_length=10)
    phone_number: str

class MomoAirtimeInitiate(BaseModel):
    amount: float = Field(..., gt=0)
    currency: str = Field(default="GHS", min_length=3, max_length=10)
    phone_number: str

class MomoBillPaymentInitiate(BaseModel):
    amount: float = Field(..., gt=0)
    currency: str = Field(default="GHS", min_length=3, max_length=10)
    biller_code: str
    customer_account_number: str
    phone_number: Optional[str] = None # For billers that identify by phone number

@router.get("/me", response_model=List[PaymentResponse])
async def get_user_payments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve all payments for the current authenticated user.
    """
    try:
        result = await db.execute(select(Payment).filter(Payment.user_id == current_user.id))
        return result.scalars().all()
    finally:
        await db.close()


@router.post("/momo/deposit/initiate", response_model=PaymentResponse, status_code=status.HTTP_202_ACCEPTED)
async def initiate_momo_deposit(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    try:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Mobile Money deposit is disabled. "
                "Use Paystack deposit instead and enter any amount from GHS 1.00."
            ),
        )
    finally:
        await db.close()


@router.post("/momo/bill/initiate", response_model=PaymentResponse, status_code=status.HTTP_202_ACCEPTED)
async def initiate_momo_bill_payment(
    bill_payment_request: MomoBillPaymentInitiate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_service: LedgerService = Depends(get_ledger_service) # Inject LedgerService
):
    try:
        if bill_payment_request.amount <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bill payment amount must be positive.")

        result = await db.execute(select(Wallet).filter(Wallet.user_id == current_user.id))
        user_wallet = result.scalars().first()
        if not user_wallet or user_wallet.balance < bill_payment_request.amount:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient wallet balance for bill payment.")
        
        # Deduct from user's wallet immediately
        user_wallet.balance -= bill_payment_request.amount
        await db.flush()

        our_ref = f"BILL_{uuid.uuid4().hex}"
        db_payment = Payment(
            user_id=current_user.id,
            processor="momo", # Assuming Momo is the processor for bill payments
            type="bill_payment",
            amount=bill_payment_request.amount,
            currency=bill_payment_request.currency,
            status="pending", # Pending external confirmation
            our_transaction_id=our_ref,
            metadata_json=json.dumps({
                "biller_code": bill_payment_request.biller_code,
                "customer_account_number": bill_payment_request.customer_account_number,
                "phone_number": bill_payment_request.phone_number
            })
        )
        db.add(db_payment)
        await db.flush()

        # Record internal transaction
        db_transaction = Transaction(
            user_id=current_user.id,
            wallet_id=user_wallet.id,
            type="bill_payment_initiate",
            amount=bill_payment_request.amount,
            status="pending"
        )
        db.add(db_transaction)
        await db.flush()

        # Create ledger entries
        await ledger_service.create_journal_entry(
            description=f"Bill Payment by user {current_user.id} for biller {bill_payment_request.biller_code}",
            ledger_entries_data=[
                {"account_name": "Customer Wallets (Liability)", "debit": bill_payment_request.amount, "credit": 0.0}, # User's wallet liability decreases
                {"account_name": "Accounts Payable (Biller)", "debit": 0.0, "credit": bill_payment_request.amount} # Our liability to the biller increases
            ],
            payment=db_payment,
            transaction=db_transaction
        )
        
        # In a real system, you would call an external bill payment service here
        # For simulation, we'll assume it's successful
        # sim_response = await bill_payment_service.process_bill_payment(...)
        sim_response = {"status": "successful", "processor_transaction_id": f"PROC_BILL_{uuid.uuid4().hex}"}


        if sim_response["status"] == "failed":
            user_wallet.balance += bill_payment_request.amount # Revert
            db_payment.status = "failed"
            db_payment.processor_transaction_id = sim_response.get("processor_transaction_id")
            db_transaction.status = "failed"
            
            # Create reversal ledger entry
            await ledger_service.create_journal_entry(
                description=f"Bill Payment Reversal for user {current_user.id} (failed)",
                ledger_entries_data=[
                    {"account_name": "Customer Wallets (Liability)", "debit": 0.0, "credit": bill_payment_request.amount}, # Revert liability decrease
                    {"account_name": "Accounts Payable (Biller)", "debit": bill_payment_request.amount, "credit": 0.0} # Revert liability increase
                ],
                payment=db_payment,
                transaction=db_transaction
            )
            await db.commit()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process bill payment.")

        db_payment.processor_transaction_id = sim_response.get("processor_transaction_id")
        db_payment.status = "successful"
        db_transaction.status = "completed"
        await db.commit()
        await db.refresh(db_payment)
        await db.refresh(db_transaction)

        return db_payment
    finally:
        await db.close()


@router.post("/momo/callback/{payment_id}", status_code=status.HTTP_200_OK) # Assuming a successful callback returns 200 OK
async def momo_callback_handler(
    payment_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    ledger_service: LedgerService = Depends(get_ledger_service),
    transaction_engine: TransactionEngine = Depends(get_transaction_engine),
):
    try:
        payload = await request.json()
        callback_status = (payload.get("status") or "").lower()
        processor_transaction_id = payload.get("processor_transaction_id")

        result = await db.execute(select(Payment).filter(Payment.id == payment_id))
        payment = result.scalars().first()
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found.")

        result = await db.execute(
            select(Transaction).filter(
                Transaction.user_id == payment.user_id,
                Transaction.type == TransactionType.FUNDING,
                Transaction.status == "pending",
            )
        )
        pending_transactions = result.scalars().all()
        transaction = None
        for tx in pending_transactions:
            metadata = json.loads(tx.metadata_json) if tx.metadata_json else {}
            if metadata.get("payment_id") == payment.id:
                transaction = tx
                break

        if not transaction:
            return {"message": "Callback received: no pending funding transaction linked to payment."}

        if transaction.status == "completed" or payment.status == "successful":
            return {"message": "Callback received: payment already processed."}

        if processor_transaction_id:
            payment.processor_transaction_id = processor_transaction_id
            transaction.provider_reference = processor_transaction_id

        if callback_status in {"successful", "success", "completed"}:
            payment.status = "successful"
            db.add(payment)
            await db.commit()
            await transaction_engine.confirm_transaction(transaction.id)
            return {"message": "Momo callback processed: wallet credited."}

        payment.status = "failed"
        transaction.status = "failed"
        db.add(payment)
        db.add(transaction)
        await db.commit()
        return {"message": "Momo callback processed: funding failed."}
    finally:
        await db.close()
