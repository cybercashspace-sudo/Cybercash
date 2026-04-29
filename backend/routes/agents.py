from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List

from backend.database import get_db
from backend.models import User, Agent, Wallet, Transaction, Payment, AgentProfile # Import Payment model
from backend.schemas.agent import AgentCreate, AgentUpdate, AgentResponse, AgentAirtimeSaleRequest, AgentDataBundleSaleRequest, AgentRegistrationRequest, AgentRegistrationResponse # Corrected import
from backend.schemas.transaction import TransactionCreate # Corrected import
from backend.schemas.agent_profile import AgentKYCSubmitSchema, AgentProfileResponse
from backend.dependencies.auth import get_current_user
from backend.core.config import settings # Import settings
from backend.services.ledger_service import LedgerService, get_ledger_service # Import LedgerService
from backend.services.momo import MomoService # Import MomoService
from backend.services.paystack_service import PaystackService, get_paystack_service # Import PaystackService
from backend.services.agent_service import AgentService, get_agent_service # Import AgentService
from backend.services.kyc_service import process_agent_kyc
from backend.services.commission_service import record_commission
from backend.services.agent_startup_loan import grant_startup_loan_credit
from backend.services.settings_service import get_or_create_platform_settings
import json # Import json
import uuid # Import uuid
import os
import re

router = APIRouter(
    prefix="/agents",
    tags=["Agents"]
)

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

    domain = str(os.getenv("PAYSTACK_FALLBACK_EMAIL_DOMAIN", "cybercash.local") or "cybercash.local").strip().lower()
    if not domain:
        domain = "cybercash.local"
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

    user_wallet.balance -= registration_fee
    db_agent = Agent(
        user_id=agent_data.user_id,
        status=agent_data.status,
        commission_rate=agent_data.commission_rate,
        float_balance=agent_data.float_balance,
    )
    db.add(db_agent)
    await db.flush()

    fee_txn = Transaction(
        user_id=agent_data.user_id,
        wallet_id=user_wallet.id,
        agent_id=db_agent.id,
        type="agent_registration_fee",
        amount=registration_fee,
        currency=user_wallet.currency,
        status="completed",
    )
    db.add(fee_txn)
    await db.flush()

    await ledger_service.create_journal_entry(
        description=f"Agent registration fee for user {agent_data.user_id}",
        ledger_entries_data=[
            {"account_name": "Customer Wallets (Liability)", "debit": registration_fee, "credit": 0.0},
            {"account_name": "Revenue - Agent Fees", "debit": 0.0, "credit": registration_fee},
        ],
        transaction=fee_txn,
    )

    await grant_startup_loan_credit(
        db,
        user_id=agent_data.user_id,
        wallet_id=user_wallet.id,
        agent=db_agent,
        amount=settings.AGENT_STARTUP_LOAN_AMOUNT,
        currency=user_wallet.currency or "GHS",
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
        if existing_agent_any and str(existing_agent_any.status or "").strip().lower() == "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already an active agent.",
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

        if registration_fee <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Agent registration fee must be positive.")

        result = await db.execute(select(Wallet).filter(Wallet.user_id == current_user.id))
        wallet = result.scalars().first()
        if not wallet:
            wallet = Wallet(user_id=current_user.id, currency="GHS", balance=0.0)
            db.add(wallet)
            await db.flush()
        
        try:
            checkout_callback_url = _checkout_status_url(request, "success")
            checkout_cancel_url = _checkout_status_url(request, "cancelled")
            payment_data = await paystack_service.initiate_payment(
                email=_resolve_paystack_email(current_user),
                amount=registration_fee * 100, # Paystack expects amount in kobo (cents)
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
                type="agent_registration_fee",
                amount=registration_fee,
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
                    f"Agent registration payment initiated (GHS {registration_fee:.2f}). "
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
            Transaction.type == "agent_registration_fee"
        ))
        transaction = result.scalars().first()

        if not transaction:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent registration transaction not found or does not belong to user.")
        
        if transaction.status == "completed":
            result = await db.execute(select(Agent).options(selectinload(Agent.user)).filter(Agent.user_id == current_user.id))
            agent = result.scalars().first()
            if agent and agent.status == "active":
                return agent
            else:
                # This should ideally not happen if transaction is completed but agent is not active
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Transaction completed but agent not active. Contact support.")

        try:
            verification_data = await paystack_service.verify_payment(reference)
            paystack_status = str(verification_data.get("status", "")).strip().lower()
            paystack_amount = float(verification_data.get("amount", 0.0) or 0.0) / 100.0
            expected_amount = float(transaction.amount or 0.0)

            if paystack_status in {"pending", "ongoing", "processing", "queued", "abandoned"}:
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

            if paystack_status == "success" and abs(paystack_amount - expected_amount) <= 0.01:
                # Mark transaction as completed
                transaction.status = "completed"
                db.add(transaction)

                # Activate the agent
                result = await db.execute(select(Agent).filter(Agent.user_id == current_user.id))
                agent = result.scalars().first()
                if not agent:
                    agent = await agent_service.create_agent(current_user.id, initial_status="pending") # Should ideally exist from initiate step
                agent = await agent_service.activate_agent(agent)

                wallet_id = transaction.wallet_id
                if not wallet_id:
                    result = await db.execute(select(Wallet).filter(Wallet.user_id == current_user.id))
                    wallet = result.scalars().first()
                    if not wallet:
                        wallet = Wallet(user_id=current_user.id, currency="GHS", balance=0.0)
                        db.add(wallet)
                        await db.flush()
                    wallet_id = wallet.id

                await grant_startup_loan_credit(
                    db,
                    user_id=current_user.id,
                    wallet_id=wallet_id,
                    agent=agent,
                    amount=settings.AGENT_STARTUP_LOAN_AMOUNT,
                    currency=transaction.currency or "GHS",
                )

                # Update user's is_agent status on the persistent DB row
                result = await db.execute(select(User).filter(User.id == current_user.id))
                persistent_user = result.scalars().first()
                if persistent_user:
                    persistent_user.is_agent = True
                    db.add(persistent_user)

                await db.commit()
                if persistent_user:
                    await db.refresh(persistent_user)
                result = await db.execute(
                    select(Agent).options(selectinload(Agent.user)).filter(Agent.id == agent.id)
                )
                refreshed_agent = result.scalars().first()
                return refreshed_agent
            else:
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

        for key, value in agent_update.model_dump(exclude_unset=True).items():
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

    commission_rate = agent.commission_rate
    commission_earned = airtime_request.amount * commission_rate
    amount_to_deduct = airtime_request.amount
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
        amount=airtime_request.amount,
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
            "commission_earned": commission_earned,
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
        amount=airtime_request.amount,
        currency=airtime_request.currency,
        commission_earned=commission_earned,
        status="completed",
        metadata_json=json.dumps({"payment_id": db_payment.id, "funding_source": funding_source})
    )
    db.add(db_transaction)
    await db.flush()

    agent.commission_balance += commission_earned
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

    await ledger_service.create_journal_entry(
        description=f"Agent {agent.id} airtime sale to {airtime_request.phone_number}",
        ledger_entries_data=[
            {
                "account_name": "Cash (Agent Float)" if funding_source == "agent_float" else "Customer Wallets (Liability)",
                "debit": amount_to_deduct if funding_source == "wallet" else 0.0,
                "credit": amount_to_deduct if funding_source == "agent_float" else 0.0,
            },
            {"account_name": "Revenue - Airtime Sales", "debit": 0.0, "credit": airtime_request.amount},
            {"account_name": "Commission Expense (Agent)", "debit": commission_earned, "credit": 0.0},
            {"account_name": "Accounts Payable (Agent Commission)", "debit": 0.0, "credit": commission_earned}
        ],
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

    commission_rate = agent.commission_rate
    commission_earned = data_bundle_request.amount * commission_rate
    amount_to_deduct = data_bundle_request.amount
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
        amount=data_bundle_request.amount,
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
            "commission_earned": commission_earned,
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
        amount=data_bundle_request.amount,
        currency=data_bundle_request.currency,
        commission_earned=commission_earned,
        status="completed",
        metadata_json=json.dumps({"payment_id": db_payment.id, "funding_source": funding_source})
    )
    db.add(db_transaction)
    await db.flush()

    agent.commission_balance += commission_earned
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

    await ledger_service.create_journal_entry(
        description=f"Agent {agent.id} data bundle sale to {data_bundle_request.phone_number}",
        ledger_entries_data=[
            {
                "account_name": "Cash (Agent Float)" if funding_source == "agent_float" else "Customer Wallets (Liability)",
                "debit": amount_to_deduct if funding_source == "wallet" else 0.0,
                "credit": amount_to_deduct if funding_source == "agent_float" else 0.0,
            },
            {"account_name": "Revenue - Data Bundle Sales", "debit": 0.0, "credit": data_bundle_request.amount},
            {"account_name": "Commission Expense (Agent)", "debit": commission_earned, "credit": 0.0},
            {"account_name": "Accounts Payable (Agent Commission)", "debit": 0.0, "credit": commission_earned}
        ],
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


@router.post("/me/kyc/submit", response_model=AgentProfileResponse, status_code=status.HTTP_200_OK)
async def submit_agent_kyc(
    payload: AgentKYCSubmitSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = await db.execute(select(Agent).filter(Agent.user_id == current_user.id))
        agent = result.scalars().first()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent profile not found.")

        kyc_result = process_agent_kyc(
            ghana_card_front_ref=payload.ghana_card_front_ref,
            ghana_card_back_ref=payload.ghana_card_back_ref,
            selfie_ref=payload.selfie_ref,
        )

        result = await db.execute(select(AgentProfile).filter(AgentProfile.user_id == current_user.id))
        profile = result.scalars().first()
        if not profile:
            profile = AgentProfile(user_id=current_user.id)

        profile.ghana_card_number = kyc_result.ghana_card_number
        profile.kyc_status = kyc_result.kyc_status
        profile.face_match_score = kyc_result.face_match_score
        profile.ghana_card_front_ref = payload.ghana_card_front_ref
        profile.ghana_card_back_ref = payload.ghana_card_back_ref
        profile.selfie_ref = payload.selfie_ref
        profile.extracted_full_name = kyc_result.full_name
        profile.extracted_dob = kyc_result.date_of_birth
        profile.extracted_expiry_date = kyc_result.expiry_date
        db.add(profile)

        # Keep agent pending until admin review.
        agent.status = "pending_kyc_review" if kyc_result.kyc_status == "pending_admin_review" else "kyc_failed"
        db.add(agent)
        await db.commit()
        await db.refresh(profile)
        return profile
    finally:
        await db.close()
