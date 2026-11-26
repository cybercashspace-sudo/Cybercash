from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
from datetime import date
import html

from backend.database import get_db
from backend.models import User, Agent, Wallet, Transaction, Payment, AgentProfile # Import Payment model
from backend.schemas.agent import AgentCreate, AgentUpdate, AgentResponse, AgentAirtimeSaleRequest, AgentDataBundleSaleRequest, AgentRegistrationRequest, AgentRegistrationResponse # Corrected import
from backend.schemas.transaction import TransactionCreate # Corrected import
from backend.dependencies.auth import get_current_user
from backend.core.config import settings # Import settings
from backend.services.ledger_service import LedgerService, get_ledger_service # Import LedgerService
from backend.services.momo import MomoService # Import MomoService
from backend.services.paystack_service import PaystackService, get_paystack_service # Import PaystackService
from backend.services.agent_service import AgentService, get_agent_service # Import AgentService
from backend.services.kyc_storage import (
    MAX_UPLOAD_BYTES,
    decrypt_identity,
    encrypt_identity,
    encrypt_image,
    normalize_image,
)
from backend.core.mailer import send_email
from backend.services.commission_service import record_commission
from backend.services.paystack_fulfillment import (
    AGENT_REGISTRATION_TX_TYPE,
    PAYSTACK_PENDING_STATUSES,
    complete_paid_agent_registration,
    ghs_to_paystack_subunit,
    paystack_amount_matches,
    paystack_currency_matches,
    to_ghs_decimal,
)
from backend.services.settings_service import get_or_create_platform_settings
from utils.network import detect_network, normalize_ghana_number
from decimal import Decimal, ROUND_HALF_UP
import json # Import json
import uuid # Import uuid
import os
import re

router = APIRouter(
    prefix="/agents",
    tags=["Agents"]
)

KYC_REVIEW_EMAIL = "Cybercashspace360@gmail.com"

momo_service = MomoService() # Initialize MomoService


def _checkout_status_url(request: Request, result: str) -> str:
    base_url = str(request.url_for("paystack_checkout_status")).strip()
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}result={str(result or '').strip().lower()}"


async def _get_agent_registration_fee(db: AsyncSession) -> float:
    platform_settings = await get_or_create_platform_settings(db)
    return float(platform_settings.agent_registration_fee or settings.AGENT_REGISTRATION_FEE)


def _resolve_paystack_email(current_user: User) -> str:
    email = str(current_user.email or "").strip().lower()
    if email and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return email

    identity = str(current_user.momo_number or current_user.phone_number or "").strip()
    digits = "".join(ch for ch in identity if ch.isdigit())
    if not digits:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid email or phone number is required for agent registration.",
        )

    domain = str(os.getenv("PAYSTACK_FALLBACK_EMAIL_DOMAIN", "cybercash.app") or "cybercash.app").strip().lower()
    if not domain:
        domain = "cybercash.app"
    return f"user{digits}@{domain}"


@router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent_profile(
    agent_data: AgentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_service: LedgerService = Depends(get_ledger_service),
):
    """
    Backward-compatible direct agent profile creation endpoint used by legacy clients/tests.
    Registration fee is deducted from the user's wallet and posted to ledger.
    New agents also receive an instant non-withdrawable startup float loan.
    """
    if agent_data.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to create this agent profile.")

    result = await db.execute(select(Agent).filter(Agent.user_id == agent_data.user_id))
    existing_agent = result.scalars().first()
    if existing_agent:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already has an agent profile")

    result = await db.execute(select(Wallet).filter(Wallet.user_id == agent_data.user_id))
    user_wallet = result.scalars().first()
    if not user_wallet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found for user")

    registration_fee = await _get_agent_registration_fee(db)
    if registration_fee <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Agent registration fee must be positive.")

    if user_wallet.balance < registration_fee:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient wallet balance to pay registration fee")

    registration_fee_amount = Decimal(str(registration_fee)).quantize(Decimal("0.01"))
    user_wallet.balance = Decimal(str(user_wallet.balance or 0)) - registration_fee_amount
    db_agent = Agent(
        user_id=agent_data.user_id,
        status="pending_kyc",
        commission_rate=agent_data.commission_rate,
        float_balance=0.0,
    )
    db.add(db_agent)
    await db.flush()

    fee_txn = Transaction(
        user_id=agent_data.user_id,
        wallet_id=user_wallet.id,
        agent_id=db_agent.id,
        type="agent_registration_fee",
        entry_type="debit",
        amount=registration_fee_amount,
        currency=user_wallet.currency,
        status="completed",
    )
    db.add(fee_txn)
    await db.flush()

    await ledger_service.create_journal_entry(
        description=f"Agent registration fee for user {agent_data.user_id}",
        ledger_entries_data=[
            {"account_name": "Customer Wallets (Liability)", "debit": registration_fee_amount, "credit": 0.0},
            {"account_name": "Revenue - Agent Fees", "debit": 0.0, "credit": registration_fee_amount},
        ],
        transaction=fee_txn,
    )

    await db.commit()
    result = await db.execute(
        select(Agent).options(selectinload(Agent.user)).filter(Agent.id == db_agent.id)
    )
    return result.scalars().first()

@router.post("/register", response_model=AgentRegistrationResponse, status_code=status.HTTP_200_OK)
async def register_agent(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    paystack_service: PaystackService = Depends(get_paystack_service),
    agent_service: AgentService = Depends(get_agent_service)
):
    """
    Initiate agent registration by processing the registration fee via Paystack.
    """
    try:
        if not current_user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Complete account verification before agent registration.",
            )
        if current_user.is_agent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already an agent."
            )

        result = await db.execute(select(Agent).filter(Agent.user_id == current_user.id))
        existing_agent_any = result.scalars().first()
        existing_status = str(getattr(existing_agent_any, "status", "") or "").strip().lower()
        if existing_agent_any and existing_status in {"active", "pending_kyc", "pending_kyc_review"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agent registration is already paid. Submit or await identity review in Settings > Security.",
            )
        
        # Check if a pending agent registration exists for this user
        result = await db.execute(select(Agent).filter(
            Agent.user_id == current_user.id,
            Agent.status == "pending"
        ))
        existing_pending_agent = result.scalars().first()

        if existing_pending_agent:
            # Check for existing pending Paystack transaction for this agent registration
            result = await db.execute(select(Transaction).filter(
                Transaction.user_id == current_user.id,
                Transaction.type == "agent_registration_fee",
                Transaction.status == "pending",
                Transaction.provider == "paystack"
            ))
            existing_transaction = result.scalars().first()
            
            if existing_transaction and existing_transaction.provider_reference:
                # Re-use existing pending payment reference
                metadata = {}
                try:
                    metadata = json.loads(existing_transaction.metadata_json or "{}")
                except Exception:
                    metadata = {}
                return AgentRegistrationResponse(
                    authorization_url=metadata.get("authorization_url"),
                    reference=existing_transaction.provider_reference,
                    message="Pending agent registration found. Please complete the payment."
                )
            else:
                # If agent pending but no transaction found, create a new one
                await db.delete(existing_pending_agent) # Clean up old pending agent record
                await db.commit()


        registration_fee = await _get_agent_registration_fee(db)
        registration_fee_ghs = to_ghs_decimal(registration_fee)

        if registration_fee_ghs <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Agent registration fee must be positive.")

        result = await db.execute(select(Wallet).filter(Wallet.user_id == current_user.id))
        wallet = result.scalars().first()
        if not wallet: # Wallet should always exist for a registered user.
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User wallet not found. Data integrity issue."
            )
        
        try:
            checkout_callback_url = _checkout_status_url(request, "success")
            checkout_cancel_url = _checkout_status_url(request, "cancelled")
            payment_data = await paystack_service.initiate_payment(
                email=_resolve_paystack_email(current_user),
                amount=ghs_to_paystack_subunit(registration_fee_ghs), # Paystack expects amount in kobo (cents)
                currency="GHS",
                metadata={
                    "user_id": str(current_user.id),
                    "purpose": "agent_registration",
                    "cancel_action": checkout_cancel_url,
                },
                callback_url=checkout_callback_url,
            )
            
            # Create a pending agent record
            agent_profile = await agent_service.create_agent(current_user.id, initial_status="pending")
            
            # Store a pending transaction in your DB for the registration fee
            transaction = Transaction(
                user_id=current_user.id,
                wallet_id=wallet.id,
                type=AGENT_REGISTRATION_TX_TYPE,
                entry_type="credit",
                amount=float(registration_fee_ghs),
                currency="GHS", # Assuming GHS
                status="pending",
                provider="paystack",
                provider_reference=payment_data["reference"],
                metadata_json=json.dumps(
                    {
                        "authorization_url": payment_data["authorization_url"],
                        "callback_url": checkout_callback_url,
                        "cancel_action": checkout_cancel_url,
                    }
                ),
            )
            db.add(transaction)
            await db.commit()
            await db.refresh(transaction)

            return AgentRegistrationResponse(
                authorization_url=payment_data["authorization_url"],
                reference=payment_data["reference"],
                message=(
                    f"Agent registration payment initiated (GHS {registration_fee_ghs:.2f}). "
                    f"After successful payment, you receive a GHS {settings.AGENT_STARTUP_LOAN_AMOUNT:.2f} "
                    "startup float loan for airtime/data resale."
                ),
            )
        except HTTPException as e:
            await db.rollback()
            raise e
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Agent registration failed: {e}")
    finally:
        await db.close()

@router.get("/register/verify/{reference}", response_model=AgentResponse)
async def verify_agent_registration(
    reference: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    paystack_service: PaystackService = Depends(get_paystack_service),
    agent_service: AgentService = Depends(get_agent_service)
):
    """
    Verify Paystack payment for agent registration and activate the agent.
    """
    try:
        result = await db.execute(select(Transaction).filter(
            Transaction.user_id == current_user.id,
            Transaction.provider == "paystack",
            Transaction.provider_reference == reference,
            Transaction.type == AGENT_REGISTRATION_TX_TYPE
        ))
        transaction = result.scalars().first()

        if not transaction:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent registration transaction not found or does not belong to user.")
        
        if transaction.status == "completed":
            return await complete_paid_agent_registration(db, transaction)

        try:
            verification_data = await paystack_service.verify_payment(reference)
            paystack_status = str(verification_data.get("status", "")).strip().lower()

            if paystack_status in PAYSTACK_PENDING_STATUSES:
                result = await db.execute(
                    select(Agent).options(selectinload(Agent.user)).filter(Agent.user_id == current_user.id)
                )
                pending_agent = result.scalars().first()
                if not pending_agent:
                    pending_agent = await agent_service.create_agent(current_user.id, initial_status="pending")
                    result = await db.execute(
                        select(Agent).options(selectinload(Agent.user)).filter(Agent.id == pending_agent.id)
                    )
                    pending_agent = result.scalars().first()
                return pending_agent

            currency_ok = paystack_currency_matches(
                verification_data.get("currency"),
                transaction.currency or "GHS",
            )
            try:
                amount_ok = paystack_amount_matches(
                    verification_data.get("amount"),
                    transaction.amount,
                )
            except ValueError:
                amount_ok = False
            if paystack_status == "success" and amount_ok and currency_ok:
                return await complete_paid_agent_registration(db, transaction)

            transaction.status = "failed"
            db.add(transaction)
            await db.commit()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Agent registration payment verification failed: {paystack_status}")
        except HTTPException as e:
            await db.rollback()
            raise e
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Agent registration verification failed: {e}")
    finally:
        await db.close()

@router.get("/me", response_model=AgentResponse)
async def get_current_user_agent_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        result = await db.execute(
            select(Agent).options(selectinload(Agent.user)).filter(Agent.user_id == current_user.id)
        )
        agent = result.scalars().first()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent profile not found for current user")
        return agent
    finally:
        await db.close()

@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: int, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(Agent).filter(Agent.id == agent_id))
        db_agent = result.scalars().first()
        if db_agent is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        return db_agent
    finally:
        await db.close()

@router.get("/", response_model=List[AgentResponse])
async def get_all_agents(db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(Agent))
        return result.scalars().all()
    finally:
        await db.close()

@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: int,
    agent_update: AgentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        result = await db.execute(select(Agent).filter(Agent.id == agent_id))
        db_agent = result.scalars().first()
        if db_agent is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        
        # Only allow the owner of the agent profile or an admin to update it
        if db_agent.user_id != current_user.id and not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this agent profile"
            )

        updates = agent_update.model_dump(exclude_unset=True)
        if not current_user.is_admin:
            protected_fields = set(updates) - {"business_name", "agent_location"}
            if protected_fields:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only an administrator can change Agent status, balance, or commission settings.",
                )
        if updates.get("status") == "active" and db_agent.status != "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Agent activation requires completed identity review. Use the KYC approval action.",
            )

        for key, value in updates.items():
            setattr(db_agent, key, value)
        
        await db.commit()
        await db.refresh(db_agent)
        return db_agent
    finally:
        await db.close()

@router.post("/me/deposit-cash", response_model=AgentResponse)
async def agent_deposit_cash(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "Agent cash deposit is disabled. "
            "Use Paystack deposit instead and enter any amount from GHS 1.00."
        ),
    )

@router.post("/me/sell-airtime", response_model=AgentResponse)
async def agent_sell_airtime(
    airtime_request: AgentAirtimeSaleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_service: LedgerService = Depends(get_ledger_service)
):
    if airtime_request.amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Airtime amount must be positive.")

    result = await db.execute(select(Agent).filter(Agent.user_id == current_user.id))
    agent = result.scalars().first()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent profile not found for current user.")
    if str(agent.status or "").strip().lower() != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent services are available after identity approval.")

    result = await db.execute(select(Wallet).filter(Wallet.user_id == current_user.id))
    user_wallet = result.scalars().first()
    if not user_wallet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found for current user.")

    phone_number = normalize_ghana_number(airtime_request.phone_number)
    if not phone_number or len(phone_number) != 10 or not phone_number.isdigit():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a valid 10-digit phone number.")

    network_provider = (airtime_request.network_provider or "").strip()
    if not network_provider or network_provider.upper() == "UNKNOWN":
        network_provider = detect_network(phone_number)
    network_provider = network_provider.upper()

    commission_rate = Decimal(str(agent.commission_rate or 0))
    sale_amount = Decimal(str(airtime_request.amount)).quantize(Decimal("0.01"))
    commission_earned = (sale_amount * commission_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    amount_to_deduct = sale_amount
    funding_source = "agent_float"
    if agent.float_balance >= amount_to_deduct:
        agent.float_balance -= amount_to_deduct
    elif user_wallet.balance >= amount_to_deduct:
        funding_source = "wallet"
        user_wallet.balance -= amount_to_deduct
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient balance. Top up agent float or wallet to continue.",
        )
    await db.flush()

    momo_response = await momo_service.initiate_airtime_payment(
        phone_number=phone_number,
        amount=float(sale_amount),
        currency=airtime_request.currency,
        network_provider=network_provider,
        user_id=current_user.id
    )
    if momo_response["status"] == "failed":
        if funding_source == "agent_float":
            agent.float_balance += amount_to_deduct
        else:
            user_wallet.balance += amount_to_deduct
        await db.commit()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=momo_response["message"])

    our_ref = f"AG_AIR_{uuid.uuid4().hex}"
    db_payment = Payment(
        user_id=current_user.id,
        agent_id=agent.id,
        processor="momo",
        type="agent_airtime_sale",
        amount=airtime_request.amount,
        currency=airtime_request.currency,
        status="successful",
        our_transaction_id=our_ref,
        processor_transaction_id=momo_response.get("processor_transaction_id"),
        metadata_json=json.dumps({
            "phone_number": phone_number,
            "network_provider": network_provider,
            "commission_earned": float(commission_earned),
            "funding_source": funding_source,
        })
    )
    db.add(db_payment)
    await db.flush()

    db_transaction = Transaction(
        user_id=current_user.id,
        wallet_id=user_wallet.id,
        agent_id=agent.id,
        type="agent_airtime_sale",
        entry_type="debit",
        amount=sale_amount,
        currency=airtime_request.currency,
        commission_earned=commission_earned,
        status="completed",
        metadata_json=json.dumps({"payment_id": db_payment.id, "funding_source": funding_source})
    )
    db.add(db_transaction)
    await db.flush()

    agent.commission_balance = Decimal(str(agent.commission_balance or 0)) + commission_earned
    db.add(agent)
    await record_commission(
        db,
        agent_id=agent.id,
        user_id=current_user.id,
        amount=commission_earned,
        currency=airtime_request.currency,
        commission_type="AGENT_AIRTIME_SALE_COMMISSION",
        status="accrued",
        transaction=db_transaction,
        metadata={
            "network_provider": network_provider,
            "phone_number": phone_number,
        },
    )

    sale_ledger_entries = (
        [
            {"account_name": "Cash (External Bank)", "debit": sale_amount, "credit": 0.0},
            {"account_name": "Cash (Agent Float)", "debit": 0.0, "credit": sale_amount},
            {"account_name": "Revenue - Airtime Sales", "debit": 0.0, "credit": sale_amount},
            {"account_name": "Agent Airtime Cost of Sales", "debit": sale_amount, "credit": 0.0},
        ]
        if funding_source == "agent_float"
        else [
            {"account_name": "Customer Wallets (Liability)", "debit": sale_amount, "credit": 0.0},
            {"account_name": "Revenue - Airtime Sales", "debit": 0.0, "credit": sale_amount},
        ]
    )
    sale_ledger_entries.extend(
        [
            {"account_name": "Commission Expense (Agent)", "debit": commission_earned, "credit": 0.0},
            {"account_name": "Accounts Payable (Agent Commission)", "debit": 0.0, "credit": commission_earned},
        ]
    )
    await ledger_service.create_journal_entry(
        description=f"Agent {agent.id} airtime sale to {airtime_request.phone_number}",
        ledger_entries_data=sale_ledger_entries,
        payment=db_payment,
        transaction=db_transaction
    )

    await db.commit()
    result = await db.execute(select(Agent).options(selectinload(Agent.user)).filter(Agent.id == agent.id))
    return result.scalars().first()

@router.post("/me/sell-data-bundle", response_model=AgentResponse)
async def agent_sell_data_bundle(
    data_bundle_request: AgentDataBundleSaleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_service: LedgerService = Depends(get_ledger_service)
):
    if data_bundle_request.amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Data bundle amount must be positive.")

    result = await db.execute(select(Agent).filter(Agent.user_id == current_user.id))
    agent = result.scalars().first()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent profile not found for current user.")
    if str(agent.status or "").strip().lower() != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent services are available after identity approval.")

    result = await db.execute(select(Wallet).filter(Wallet.user_id == current_user.id))
    user_wallet = result.scalars().first()
    if not user_wallet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found for current user.")

    phone_number = normalize_ghana_number(data_bundle_request.phone_number)
    if not phone_number or len(phone_number) != 10 or not phone_number.isdigit():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a valid 10-digit phone number.")

    network_provider = (data_bundle_request.network_provider or "").strip()
    if not network_provider or network_provider.upper() == "UNKNOWN":
        network_provider = detect_network(phone_number)
    network_provider = network_provider.upper()

    commission_rate = Decimal(str(agent.commission_rate or 0))
    sale_amount = Decimal(str(data_bundle_request.amount)).quantize(Decimal("0.01"))
    commission_earned = (sale_amount * commission_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    amount_to_deduct = sale_amount
    funding_source = "agent_float"
    if agent.float_balance >= amount_to_deduct:
        agent.float_balance -= amount_to_deduct
    elif user_wallet.balance >= amount_to_deduct:
        funding_source = "wallet"
        user_wallet.balance -= amount_to_deduct
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient balance. Top up agent float or wallet to continue.",
        )
    await db.flush()

    momo_response = await momo_service.initiate_data_bundle_payment(
        phone_number=phone_number,
        amount=float(sale_amount),
        currency=data_bundle_request.currency,
        network_provider=network_provider,
        user_id=current_user.id
    )
    if momo_response["status"] == "failed":
        if funding_source == "agent_float":
            agent.float_balance += amount_to_deduct
        else:
            user_wallet.balance += amount_to_deduct
        await db.commit()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=momo_response["message"])

    our_ref = f"AG_DATA_{uuid.uuid4().hex}"
    db_payment = Payment(
        user_id=current_user.id,
        agent_id=agent.id,
        processor="momo",
        type="agent_data_bundle_sale",
        amount=data_bundle_request.amount,
        currency=data_bundle_request.currency,
        status="successful",
        our_transaction_id=our_ref,
        processor_transaction_id=momo_response.get("processor_transaction_id"),
        metadata_json=json.dumps({
            "phone_number": phone_number,
            "network_provider": network_provider,
            "commission_earned": float(commission_earned),
            "funding_source": funding_source,
        })
    )
    db.add(db_payment)
    await db.flush()

    db_transaction = Transaction(
        user_id=current_user.id,
        wallet_id=user_wallet.id,
        agent_id=agent.id,
        type="agent_data_bundle_sale",
        entry_type="debit",
        amount=sale_amount,
        currency=data_bundle_request.currency,
        commission_earned=commission_earned,
        status="completed",
        metadata_json=json.dumps({"payment_id": db_payment.id, "funding_source": funding_source})
    )
    db.add(db_transaction)
    await db.flush()

    agent.commission_balance = Decimal(str(agent.commission_balance or 0)) + commission_earned
    db.add(agent)
    await record_commission(
        db,
        agent_id=agent.id,
        user_id=current_user.id,
        amount=commission_earned,
        currency=data_bundle_request.currency,
        commission_type="AGENT_DATA_SALE_COMMISSION",
        status="accrued",
        transaction=db_transaction,
        metadata={
            "network_provider": network_provider,
            "phone_number": phone_number,
        },
    )

    sale_ledger_entries = (
        [
            {"account_name": "Cash (External Bank)", "debit": sale_amount, "credit": 0.0},
            {"account_name": "Cash (Agent Float)", "debit": 0.0, "credit": sale_amount},
            {"account_name": "Revenue - Data Bundle Sales", "debit": 0.0, "credit": sale_amount},
            {"account_name": "Agent Data Bundle Cost of Sales", "debit": sale_amount, "credit": 0.0},
        ]
        if funding_source == "agent_float"
        else [
            {"account_name": "Customer Wallets (Liability)", "debit": sale_amount, "credit": 0.0},
            {"account_name": "Revenue - Data Bundle Sales", "debit": 0.0, "credit": sale_amount},
        ]
    )
    sale_ledger_entries.extend(
        [
            {"account_name": "Commission Expense (Agent)", "debit": commission_earned, "credit": 0.0},
            {"account_name": "Accounts Payable (Agent Commission)", "debit": 0.0, "credit": commission_earned},
        ]
    )
    await ledger_service.create_journal_entry(
        description=f"Agent {agent.id} data bundle sale to {data_bundle_request.phone_number}",
        ledger_entries_data=sale_ledger_entries,
        payment=db_payment,
        transaction=db_transaction
    )

    await db.commit()
    result = await db.execute(select(Agent).options(selectinload(Agent.user)).filter(Agent.id == agent.id))
    return result.scalars().first()

@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        result = await db.execute(select(Agent).filter(Agent.id == agent_id))
        db_agent = result.scalars().first()
        if db_agent is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        
        # Only allow the owner or an admin to delete the agent profile
        if db_agent.user_id != current_user.id and not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this agent profile"
            )

        await db.delete(db_agent)
        await db.commit()
        return {"message": "Agent deleted successfully"}
    finally:
        await db.close()


async def _read_kyc_image(upload: UploadFile) -> bytes:
    raw = await upload.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Each identity photo must be smaller than 4 MB.")
    try:
        normalized, _mime = normalize_image(raw)
        return normalized
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _get_paid_agent_for_kyc(db: AsyncSession, user_id: int) -> Agent:
    agent_result = await db.execute(select(Agent).filter(Agent.user_id == user_id))
    agent = agent_result.scalars().first()
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Complete the agent registration payment before submitting identity documents.",
        )
    payment_result = await db.execute(
        select(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.type == AGENT_REGISTRATION_TX_TYPE,
            Transaction.status == "completed",
        ).order_by(Transaction.id.desc())
    )
    if not payment_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your agent registration payment has not been confirmed yet.",
        )
    return agent


@router.get("/me/kyc", status_code=status.HTTP_200_OK)
async def get_my_agent_kyc_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        agent = await _get_paid_agent_for_kyc(db, current_user.id)
        result = await db.execute(select(AgentProfile).filter(AgentProfile.user_id == current_user.id))
        profile = result.scalars().first()
        return {
            "agent_id": agent.id,
            "agent_status": agent.status,
            "kyc_status": profile.kyc_status if profile else "not_submitted",
            "submitted_at": profile.created_at.isoformat() if profile and profile.created_at else None,
        }
    finally:
        await db.close()


@router.post("/me/kyc/submit", status_code=status.HTTP_200_OK)
async def submit_agent_kyc(
    full_name: str = Form(..., min_length=2, max_length=120),
    date_of_birth: str = Form(...),
    ghana_card_number: str = Form(..., min_length=13, max_length=15),
    consent: bool = Form(...),
    ghana_card_front: UploadFile = File(...),
    ghana_card_back: UploadFile = File(...),
    selfie_with_id: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        agent = await _get_paid_agent_for_kyc(db, current_user.id)
        name = " ".join(str(full_name or "").split())
        if len(name) < 2 or any(ord(character) < 32 for character in name):
            raise HTTPException(status_code=400, detail="Enter your full legal name.")
        try:
            dob = date.fromisoformat(str(date_of_birth or "").strip())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Enter your date of birth in YYYY-MM-DD format.") from exc
        if dob >= date.today():
            raise HTTPException(status_code=400, detail="Date of birth must be in the past.")
        card_number = str(ghana_card_number or "").strip().upper()
        if not re.fullmatch(r"GHA-\d{9}-\d", card_number):
            raise HTTPException(status_code=400, detail="Enter the full Ghana Card number, for example GHA-123456789-0.")
        if not consent:
            raise HTTPException(status_code=400, detail="Confirm that the details and photos are yours before submitting.")

        profile_result = await db.execute(select(AgentProfile).filter(AgentProfile.user_id == current_user.id))
        profile = profile_result.scalars().first()
        if profile and profile.kyc_status in {"pending_admin_review", "approved"}:
            raise HTTPException(status_code=409, detail="Your identity submission is already under review or approved.")
        if agent.status == "active":
            raise HTTPException(status_code=409, detail="This agent account is already active.")

        front_bytes, back_bytes, selfie_bytes = await _read_kyc_image(ghana_card_front), await _read_kyc_image(ghana_card_back), await _read_kyc_image(selfie_with_id)
        # Fail before changing the record if the deployment has no usable key.
        identity_encrypted = encrypt_identity(name, dob.isoformat(), card_number)
        front_encrypted, back_encrypted, selfie_encrypted = (
            encrypt_image(front_bytes), encrypt_image(back_bytes), encrypt_image(selfie_bytes)
        )
        if not profile:
            profile = AgentProfile(user_id=current_user.id)
        profile.kyc_status = "pending_admin_review"
        profile.face_match_score = None
        profile.ghana_card_number = None
        profile.extracted_full_name = None
        profile.extracted_dob = None
        profile.extracted_expiry_date = None
        profile.identity_data_encrypted = identity_encrypted
        profile.ghana_card_front_encrypted = front_encrypted
        profile.ghana_card_back_encrypted = back_encrypted
        profile.selfie_encrypted = selfie_encrypted
        # Legacy plaintext/reference fields are intentionally cleared.
        profile.ghana_card_front_ref = None
        profile.ghana_card_back_ref = None
        profile.selfie_ref = None
        agent.status = "pending_kyc_review"
        db.add(profile)
        db.add(agent)
        await db.commit()
        await db.refresh(profile)

        reference = f"AGENT-KYC-{agent.id}-{profile.created_at.strftime('%Y%m%d') if profile.created_at else 'NEW'}"
        try:
            mail_result = await send_email(
                "CyberCash agent identity review requested",
                [KYC_REVIEW_EMAIL],
                (
                    "<p>A new agent identity submission is ready for review in the CyberCash Admin Dashboard.</p>"
                    f"<p>Reference: <strong>{html.escape(reference)}</strong></p>"
                    "<p>For security, identity numbers and photos are available only through the authenticated admin review screen.</p>"
                ),
                idempotency_key=f"agent-kyc-submission-{agent.id}-{profile.id}",
            )
        except Exception:
            mail_result = {"status": "error"}
        return {
            "agent_id": agent.id,
            "kyc_status": profile.kyc_status,
            "reference": reference,
            "notification_sent": str((mail_result or {}).get("status", "")).lower() in {"queued", "sent", "delivered"},
        }
    except HTTPException:
        raise
    except RuntimeError as exc:
        await db.rollback()
        raise HTTPException(status_code=503, detail="Secure identity storage is not available. Please try again later.") from exc
    finally:
        await db.close()
