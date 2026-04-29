from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import List, Optional
from datetime import datetime, timezone
import json

from .. import schemas # Added import

from backend.database import get_db
from backend.models import (
    Account,
    Agent,
    AgentProfile,
    CryptoTransaction,
    CryptoWallet,
    LedgerEntry,
    LoanApplication,
    Payment,
    Transaction,
    User,
    Wallet,
)
from backend.models import BundleCatalog
from backend.schemas.agent import AgentResponse, AgentUpdate # Corrected import
from backend.schemas.account import AccountResponse # Corrected import
from backend.schemas.payment import PaymentResponse # Corrected import
from backend.schemas.cryptotransaction import CryptoTransactionResponse # Corrected import
from backend.schemas.transaction import TransactionResponse # New Import
from backend.schemas.user import UserResponse
from backend.schemas.admin import (
    WithdrawalApprovalRequest,
    BankWithdrawalInitiateRequest,
    MomoWithdrawalInitiateRequest,
    AdminCryptoWithdrawalInitiateRequest
)
from backend.schemas.wallet import WalletResponse # New Import
from backend.schemas.loan_admin import LoanOverviewResponse, AgentCreditProfileResponse, LoanPolicyUpdateRequest # New Import
from backend.schemas.loan_admin import LoanApplicationDecisionRequest
from backend.schemas.loan_application import LoanApplicationInDB
from backend.schemas.bundle import BundleCatalogCreate, BundleCatalogResponse, BundleCatalogUpdate
from backend.dependencies.auth import get_current_user
from backend.core.config import settings
from backend.services.ledger_service import LedgerService, get_ledger_service
from backend.services.momo import MomoService
from backend.services.crypto import CryptoService
from backend.services.bank import BankService, get_bank_service # New import
from backend.services.payout_service import PayoutService, get_payout_service
from backend.services.settings_service import get_or_create_platform_settings
from backend.services import loan_service # New Import

router = APIRouter(prefix="/admin", tags=["Admin"])

momo_service = MomoService()
crypto_service = CryptoService()
bank_service = BankService() # Initialize BankService

def get_admin_user(current_user: User = Depends(get_current_user)):
    role = str(getattr(current_user, "role", "") or "").strip().lower()
    if not bool(getattr(current_user, "is_admin", False)) and role not in {"admin", "super_admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can perform this action"
        )
    return current_user


@router.get("/bundles", response_model=List[BundleCatalogResponse])
async def list_bundle_catalog(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    try:
        result = await db.execute(select(BundleCatalog).order_by(BundleCatalog.network, BundleCatalog.bundle_code))
        return result.scalars().all()
    finally:
        await db.close()


@router.post("/bundles", response_model=BundleCatalogResponse, status_code=status.HTTP_201_CREATED)
async def create_bundle_catalog_item(
    request: BundleCatalogCreate,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    try:
        result = await db.execute(
            select(BundleCatalog).filter(
                BundleCatalog.network == request.network.upper(),
                BundleCatalog.bundle_code == request.bundle_code.upper(),
            )
        )
        existing = result.scalars().first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bundle code already exists for network.")

        bundle = BundleCatalog(
            network=request.network.upper(),
            bundle_code=request.bundle_code.upper(),
            amount=request.amount,
            currency=request.currency.upper(),
            provider=request.provider.lower(),
            is_active=request.is_active,
            metadata_json=request.metadata_json,
        )
        db.add(bundle)
        await db.commit()
        await db.refresh(bundle)
        return bundle
    finally:
        await db.close()


@router.put("/bundles/{bundle_id}", response_model=BundleCatalogResponse)
async def update_bundle_catalog_item(
    bundle_id: int,
    request: BundleCatalogUpdate,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    try:
        result = await db.execute(select(BundleCatalog).filter(BundleCatalog.id == bundle_id))
        bundle = result.scalars().first()
        if not bundle:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bundle not found.")

        updates = request.model_dump(exclude_unset=True)
        if "currency" in updates and updates["currency"] is not None:
            updates["currency"] = updates["currency"].upper()
        if "provider" in updates and updates["provider"] is not None:
            updates["provider"] = updates["provider"].lower()

        for key, value in updates.items():
            setattr(bundle, key, value)

        db.add(bundle)
        await db.commit()
        await db.refresh(bundle)
        return bundle
    finally:
        await db.close()

@router.get("/health")
def health(admin_user: User = Depends(get_admin_user)):
    return {"status": "ok"}


@router.get("/dashboard")
async def get_admin_dashboard(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    """
    Summary metrics for the Admin Dashboard (admin only).
    """
    from backend.core.transaction_types import TransactionType

    deposit_types = {
        TransactionType.FUNDING,
        TransactionType.AGENT_DEPOSIT,
        TransactionType.CARD_LOAD,
        TransactionType.BTC_DEPOSIT,
        TransactionType.INVESTMENT_CREATE,
    }
    withdrawal_types = {
        TransactionType.AGENT_WITHDRAWAL,
        TransactionType.MOBILE_MONEY,
        TransactionType.CARD_WITHDRAW,
        TransactionType.BTC_WITHDRAW,
        TransactionType.INVESTMENT_PAYOUT,
    }

    def _activity_label(tx_type: str) -> str:
        key = str(tx_type or "").strip().upper()
        mapping = {
            TransactionType.AGENT_DEPOSIT: "Cash Deposit (Agent)",
            TransactionType.AGENT_WITHDRAWAL: "User Withdrawal",
            TransactionType.BTC_DEPOSIT: "BTC Deposit",
            TransactionType.BTC_WITHDRAW: "BTC Withdrawal",
            TransactionType.AIRTIME: "Airtime Conversion",
            TransactionType.DATA: "Data Bundle Purchase",
            TransactionType.FUNDING: "Wallet Funding",
            TransactionType.TRANSFER: "P2P Transfer",
            TransactionType.MOBILE_MONEY: "Mobile Money Payout",
            TransactionType.ESCROW_CREATE: "Escrow Created",
            TransactionType.ESCROW_RELEASE: "Escrow Released",
            TransactionType.CARD_SPEND: "Card Spend",
            TransactionType.CARD_LOAD: "Card Load",
            TransactionType.CARD_WITHDRAW: "Card Withdrawal",
            TransactionType.INVESTMENT_CREATE: "Investment Deposit",
            TransactionType.INVESTMENT_PAYOUT: "Investment Payout",
            TransactionType.LOAN_DISBURSE: "Loan Disbursed",
            TransactionType.LOAN_REPAY: "Loan Repayment",
        }
        return mapping.get(key, key.replace("_", " ").title() if key else "Activity")

    try:
        users = (
            await db.execute(select(func.count(User.id)))
        ).scalar_one()
        agents = (
            await db.execute(select(func.count(Agent.id)))
        ).scalar_one()
        active_agents = (
            await db.execute(select(func.count(Agent.id)).where(Agent.status == "active"))
        ).scalar_one()

        platform_balance = (
            await db.execute(
                select(
                    func.coalesce(
                        func.sum(Wallet.balance + Wallet.escrow_balance + Wallet.investment_balance),
                        0.0,
                    )
                ).where(Wallet.currency == "GHS")
            )
        ).scalar_one()

        total_deposits = (
            await db.execute(
                select(func.coalesce(func.sum(func.abs(Transaction.amount)), 0.0)).where(
                    Transaction.status == "completed",
                    Transaction.currency == "GHS",
                    Transaction.type.in_(deposit_types),
                )
            )
        ).scalar_one()

        total_withdrawals = (
            await db.execute(
                select(func.coalesce(func.sum(func.abs(Transaction.amount)), 0.0)).where(
                    Transaction.status == "completed",
                    Transaction.currency == "GHS",
                    Transaction.type.in_(withdrawal_types),
                )
            )
        ).scalar_one()

        revenue = (
            await db.execute(
                select(func.coalesce(func.sum(LedgerEntry.credit), 0.0))
                .select_from(LedgerEntry)
                .join(Account, LedgerEntry.account_id == Account.id)
                .where(Account.type == "Revenue")
            )
        ).scalar_one()

        btc_volume = (
            await db.execute(
                select(func.coalesce(func.sum(CryptoTransaction.amount), 0.0)).where(
                    CryptoTransaction.coin_type == "BTC",
                    CryptoTransaction.status != "failed",
                )
            )
        ).scalar_one()

        activity_rows = (
            await db.execute(
                select(Transaction.type, Transaction.amount, Transaction.timestamp)
                .where(Transaction.status == "completed")
                .order_by(Transaction.timestamp.desc())
                .limit(12)
            )
        ).all()

        activity = []
        seen_labels = set()
        for row in activity_rows:
            label = _activity_label(row.type)
            if label in seen_labels:
                continue
            seen_labels.add(label)
            activity.append(
                {
                    "label": label,
                    "amount": float(row.amount or 0.0),
                    "timestamp": row.timestamp.isoformat() if row.timestamp else "",
                }
            )
            if len(activity) >= 6:
                break

        return {
            "platform_balance": float(platform_balance or 0.0),
            "users": int(users or 0),
            "agents": int(agents or 0),
            "active_agents": int(active_agents or 0),
            "total_deposits": float(total_deposits or 0.0),
            "withdrawals": float(total_withdrawals or 0.0),
            "revenue": float(revenue or 0.0),
            "btc_volume": float(btc_volume or 0.0),
            "activity": activity,
        }
    finally:
        await db.close()


@router.get("/users", response_model=List[UserResponse])
async def list_users_admin(
    status: Optional[str] = None,
    role: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    """
    List users (admin only). Supports basic status/role filtering and free-text search.
    """
    try:
        capped_limit = max(1, min(int(limit or 50), 200))
        capped_offset = max(0, int(offset or 0))

        query = select(User).order_by(User.created_at.desc()).limit(capped_limit).offset(capped_offset)

        if status:
            query = query.where(User.status == status)
        if role:
            query = query.where(User.role == role)
        if q:
            needle = f"%{str(q).strip()}%"
            query = query.where(
                or_(
                    User.full_name.ilike(needle),
                    User.phone_number.ilike(needle),
                    User.momo_number.ilike(needle),
                    User.email.ilike(needle),
                )
            )

        result = await db.execute(query)
        return result.scalars().all()
    finally:
        await db.close()


@router.put("/users/{user_id}/status", response_model=UserResponse)
async def update_user_status_admin(
    user_id: int,
    request: schemas.admin.UserStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    """
    Suspend or reactivate a user account (admin only).
    """
    try:
        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalars().first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

        new_status = str(getattr(request, "status", "") or "").strip().lower()
        target_role = str(getattr(user, "role", "") or "").strip().lower()
        target_is_admin = bool(getattr(user, "is_admin", False)) or target_role in {"admin", "super_admin"}
        if target_is_admin and new_status != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin accounts cannot be suspended.",
            )
        user.status = new_status
        user.is_active = new_status == "active"

        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user
    finally:
        await db.close()


@router.get("/loans/overview", response_model=LoanOverviewResponse)
async def get_loan_overview_admin(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    Retrieve an overview of all active loans, total exposure, and repayment metrics (admin only).
    """
    try:
        return await loan_service.get_loan_overview(db=db)
    finally:
        await db.close()


@router.get("/loans/applications/pending", response_model=List[LoanApplicationInDB])
async def get_pending_loan_applications_admin(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    try:
        result = await db.execute(
            select(LoanApplication).filter(LoanApplication.status == "pending_admin_approval")
        )
        return result.scalars().all()
    finally:
        await db.close()


@router.post("/loans/applications/{application_id}/decision", response_model=LoanApplicationInDB)
async def decide_loan_application_admin(
    application_id: int,
    request: LoanApplicationDecisionRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    try:
        if request.decision == "rejected":
            application = await loan_service.reject_loan_application(
                db=db,
                application_id=application_id,
                admin_user_id=admin_user.id,
                review_note=request.review_note,
            )
        else:
            application = await loan_service.approve_loan_application(
                db=db,
                application_id=application_id,
                admin_user_id=admin_user.id,
                approved_amount=request.approved_amount,
                fee_percentage=request.fee_percentage,
                offered_repayment_duration=request.offered_repayment_duration,
                review_note=request.review_note,
            )

        if not application:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan application not found.")
        return application
    finally:
        await db.close()

@router.get("/loans/agent/{agent_id}/profile", response_model=AgentCreditProfileResponse)
async def get_agent_credit_profile_admin(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    Retrieve the credit profile for a specific agent (admin only).
    """
    try:
        profile = await loan_service.get_agent_credit_profile(db=db, agent_id=agent_id)
        if not profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent credit profile not found.")
        return profile
    finally:
        await db.close()

@router.put("/loans/policy", response_model=dict)
def update_loan_policy_admin(
    request: LoanPolicyUpdateRequest,
    admin_user: User = Depends(get_admin_user)
):
    """
    Update global loan policy settings (admin only).
    Note: In a production system, these settings might be stored in the DB
    and loaded dynamically, rather than directly updating os.environ.
    For this example, we'll directly update the settings object.
    """
    if request.max_loan_amount_per_agent is not None:
        settings.MAX_LOAN_AMOUNT_PER_AGENT = request.max_loan_amount_per_agent
    if request.default_penalty_fee_percentage is not None:
        settings.DEFAULT_PENALTY_FEE_PERCENTAGE = request.default_penalty_fee_percentage
    if request.risk_score_approval_threshold is not None:
        settings.RISK_SCORE_APPROVAL_THRESHOLD = request.risk_score_approval_threshold
    
    return {"message": "Loan policy settings updated successfully."}

@router.get("/transactions", response_model=List[TransactionResponse])
async def get_all_transactions_admin(
    user_id: Optional[int] = None,
    type: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    Retrieve all transactions in the system with optional filters (admin only).
    """
    try:
        query = select(Transaction)
        if user_id:
            query = query.filter(Transaction.user_id == user_id)
        if type:
            query = query.filter(Transaction.type == type)
        if status:
            query = query.filter(Transaction.status == status)
        result = await db.execute(query)
        return result.scalars().all()
    finally:
        await db.close()

@router.get("/users/{user_id}/wallet", response_model=WalletResponse)
async def get_user_wallet_admin(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    Retrieve a specific user's wallet details (admin only).
    """
    try:
        result = await db.execute(select(Wallet).filter(Wallet.user_id == user_id))
        user_wallet = result.scalars().first()
        if not user_wallet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User wallet not found.")
        return user_wallet
    finally:
        await db.close()

@router.get("/wallets", response_model=List[WalletResponse])
async def get_all_wallets_admin(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    Retrieve all wallets in the system (admin only).
    """
    try:
        result = await db.execute(select(Wallet))
        wallets = result.scalars().all()
        return wallets
    finally:
        await db.close()

@router.get("/agents", response_model=List[AgentResponse])
async def get_all_agents_admin(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    try:
        query = select(Agent)
        if status:
            query = query.filter(Agent.status == status)
        result = await db.execute(query)
        return result.scalars().all()
    finally:
        await db.close()

@router.put("/agents/{agent_id}/approve", response_model=AgentResponse)
async def approve_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    try:
        result = await db.execute(select(Agent).filter(Agent.id == agent_id))
        db_agent = result.scalars().first()
        if db_agent is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        
        if db_agent.status == "active":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Agent is already active")

        db_agent.status = "active"
        await db.commit()
        await db.refresh(db_agent)
        return db_agent
    finally:
        await db.close()


@router.put("/agents/{agent_id}/kyc-approve", response_model=AgentResponse)
async def approve_agent_kyc_and_activate(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    try:
        result = await db.execute(select(Agent).filter(Agent.id == agent_id))
        db_agent = result.scalars().first()
        if not db_agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

        result = await db.execute(select(AgentProfile).filter(AgentProfile.user_id == db_agent.user_id))
        profile = result.scalars().first()
        if not profile:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Agent KYC profile missing.")
        if float(profile.face_match_score or 0.0) < 90.0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Face match score below threshold.")

        profile.kyc_status = "approved"
        profile.reviewed_by_admin_id = admin_user.id
        profile.reviewed_at = datetime.now(timezone.utc)
        db.add(profile)

        db_agent.status = "active"
        db.add(db_agent)

        result = await db.execute(select(User).filter(User.id == db_agent.user_id))
        linked_user = result.scalars().first()
        if linked_user:
            linked_user.is_agent = True
            linked_user.kyc_tier = 3
            linked_user.daily_limit = max(float(linked_user.daily_limit or 0.0), 50000.0)
            db.add(linked_user)

        await db.commit()
        await db.refresh(db_agent)
        return db_agent
    finally:
        await db.close()

@router.put("/agents/{agent_id}/commission", response_model=AgentResponse)
async def update_agent_commission(
    agent_id: int,
    commission_rate: float,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    try:
        if not (0 <= commission_rate <= 1):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Commission rate must be between 0 and 1")

        result = await db.execute(select(Agent).filter(Agent.id == agent_id))
        db_agent = result.scalars().first()
        if db_agent is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        
        db_agent.commission_rate = commission_rate
        await db.commit()
        await db.refresh(db_agent)
        return db_agent
    finally:
        await db.close()

@router.put("/agents/{agent_id}/freeze-borrowing", response_model=AgentResponse)
async def freeze_agent_borrowing(
    agent_id: int,
    request: schemas.admin.AgentBorrowingFreezeRequest, # Use the new schema
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    try:
        result = await db.execute(select(Agent).filter(Agent.id == agent_id))
        db_agent = result.scalars().first()
        if db_agent is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        
        db_agent.is_borrowing_frozen = request.is_borrowing_frozen
        await db.commit()
        await db.refresh(db_agent)
        return db_agent
    finally:
        await db.close()

@router.put("/users/{user_id}/wallets/{wallet_id}/freeze", response_model=WalletResponse)
async def freeze_user_wallet(
    user_id: int,
    wallet_id: int,
    request: schemas.admin.WalletFreezeRequest, # Use the new schema
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    try:
        result = await db.execute(select(Wallet).filter(
            Wallet.id == wallet_id,
            Wallet.user_id == user_id
        ))
        db_wallet = result.scalars().first()
        if db_wallet is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found for this user.")
        
        db_wallet.is_frozen = request.is_frozen
        await db.commit()
        await db.refresh(db_wallet)
        return db_wallet
    finally:
        await db.close()

@router.get("/settings/agent-registration-fee", response_model=float)
async def get_agent_registration_fee(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    platform_settings = await get_or_create_platform_settings(db)
    return float(platform_settings.agent_registration_fee or settings.AGENT_REGISTRATION_FEE)

@router.get("/accounts", response_model=List[AccountResponse])
async def get_all_ledger_accounts(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    Retrieves all ledger accounts with their current balances.
    """
    try:
        result = await db.execute(select(Account))
        return result.scalars().all()
    finally:
        await db.close()

@router.get("/withdrawals/fiat", response_model=List[PaymentResponse])
async def get_pending_fiat_withdrawals(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    Lists all fiat (Momo) withdrawals that are pending admin approval.
    """
    try:
        result = await db.execute(select(Payment).filter(
            Payment.type == "withdrawal",
            Payment.processor == "momo",
            Payment.status == "pending_admin_approval"
        ))
        return result.scalars().all()
    finally:
        await db.close()

@router.put("/withdrawals/fiat/{payment_id}/approve-reject", response_model=PaymentResponse)
async def approve_reject_fiat_withdrawal(
    payment_id: int,
    request: WithdrawalApprovalRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    ledger_service: LedgerService = Depends(get_ledger_service)
):
    try:
        result = await db.execute(select(Payment).filter(Payment.id == payment_id))
        db_payment = result.scalars().first()
        if not db_payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment record not found.")

        if db_payment.status != "pending_admin_approval":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Withdrawal is not pending admin approval.")

        result = await db.execute(select(Wallet).filter(Wallet.user_id == db_payment.user_id))
        user_wallet = result.scalars().first()
        if not user_wallet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User wallet not found for payment.")
        
        # Find the associated internal transaction
        result = await db.execute(select(Transaction).filter(
            Transaction.user_id == db_payment.user_id,
            Transaction.wallet_id == user_wallet.id,
            Transaction.type == "momo_withdrawal_initiate",
            Transaction.amount == db_payment.amount,
            Transaction.status == "pending_admin_approval"
        ))
        db_transaction = result.scalars().first()
        if not db_transaction:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated internal transaction not found.")


        if request.status == "approved":
            # Initiate actual Momo withdrawal
            momo_response = await momo_service.initiate_withdrawal(
                phone_number=json.loads(db_payment.metadata_json).get("phone_number"),
                amount=db_payment.amount,
                currency=db_payment.currency,
                user_id=db_payment.user_id,
                callback_url=f"http://localhost:8000/payments/momo/callback/{db_payment.id}" # Example callback
            )

            if momo_response["status"] == "failed":
                # Revert wallet balance (already deducted optimistically)
                user_wallet.balance += db_payment.amount
                db_payment.status = "failed"
                db_transaction.status = "failed"
                db_payment.processor_transaction_id = momo_response.get("processor_transaction_id")
                
                # Create reversal ledger entry
                await ledger_service.create_journal_entry(
                    description=f"Admin Reject Momo Withdrawal for user {db_payment.user_id} (Momo initiation failed)",
                    ledger_entries_data=[
                        {"account_name": "Customer Wallets (Liability)", "debit": 0.0, "credit": db_payment.amount}, # Revert liability decrease
                        {"account_name": "Cash (External Bank)", "debit": db_payment.amount, "credit": 0.0} # Revert external cash decrease
                    ],
                    payment=db_payment,
                    transaction=db_transaction
                )
                await db.commit()
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=momo_response["message"])
            
            db_payment.status = "awaiting_confirmation"
            db_transaction.status = "awaiting_confirmation"
            db_payment.processor_transaction_id = momo_response.get("processor_transaction_id")
            await db.commit()
            await db.refresh(db_payment)
            await db.refresh(db_transaction)
        
        elif request.status == "rejected":
            # Revert wallet balance (already deducted optimistically)
            user_wallet.balance += db_payment.amount
            db_payment.status = "rejected"
            db_transaction.status = "rejected"
            db_payment.metadata_json = json.dumps({**json.loads(db_payment.metadata_json), "admin_rejection_reason": request.reason})

            # Create reversal ledger entry
            await ledger_service.create_journal_entry(
                description=f"Admin Reject Momo Withdrawal for user {db_payment.user_id}",
                ledger_entries_data=[
                    {"account_name": "Customer Wallets (Liability)", "debit": 0.0, "credit": db_payment.amount}, # Revert liability decrease
                    {"account_name": "Cash (External Bank)", "debit": db_payment.amount, "credit": 0.0} # Revert external cash decrease
                ],
                payment=db_payment,
                transaction=db_transaction
            )
            await db.commit()
            await db.refresh(db_payment)
            await db.refresh(db_transaction)
        
        return db_payment
    finally:
        await db.close()

@router.get("/withdrawals/crypto", response_model=List[CryptoTransactionResponse])
async def get_pending_crypto_withdrawals(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    Lists all crypto withdrawals that are pending admin approval.
    """
    try:
        result = await db.execute(select(CryptoTransaction).filter(
            CryptoTransaction.type == "withdrawal",
            CryptoTransaction.status == "pending_admin_approval"
        ))
        return result.scalars().all()
    finally:
        await db.close()

@router.put("/withdrawals/crypto/{crypto_transaction_id}/approve-reject", response_model=CryptoTransactionResponse)
async def approve_reject_crypto_withdrawal(
    crypto_transaction_id: int,
    request: WithdrawalApprovalRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    ledger_service: LedgerService = Depends(get_ledger_service)
):
    try:
        result = await db.execute(select(CryptoTransaction).filter(CryptoTransaction.id == crypto_transaction_id))
        db_crypto_transaction = result.scalars().first()
        if not db_crypto_transaction:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crypto transaction not found.")

        if db_crypto_transaction.status != "pending_admin_approval":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Crypto withdrawal is not pending admin approval.")

        result = await db.execute(select(CryptoWallet).filter(
            CryptoWallet.id == db_crypto_transaction.crypto_wallet_id
        ))
        user_crypto_wallet = result.scalars().first()
        if not user_crypto_wallet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User crypto wallet not found for transaction.")

        # Calculate total amount to revert/deduct (amount + fee)
        total_amount = db_crypto_transaction.amount + db_crypto_transaction.fee


        if request.status == "approved":
            # Initiate actual crypto withdrawal
            crypto_response = await crypto_service.initiate_withdrawal(
                from_address="OUR_HOT_WALLET_ADDRESS", # Placeholder
                to_address=db_crypto_transaction.to_address,
                coin_type=db_crypto_transaction.coin_type,
                amount=db_crypto_transaction.amount
            )

            if crypto_response["status"] == "failed":
                # Revert balance (already deducted optimistically)
                user_crypto_wallet.balance += total_amount
                db_crypto_transaction.status = "failed"

                # Create reversal ledger entry
                await ledger_service.create_journal_entry(
                    description=f"Admin Reject Crypto Withdrawal for user {db_crypto_transaction.user_id} (Crypto initiation failed)",
                    ledger_entries_data=[
                        {"account_name": "Customer Crypto Balances (Liability)", "debit": 0.0, "credit": total_amount}, # Revert liability decrease
                        {"account_name": "Crypto Hot Wallet (Asset)", "debit": total_amount, "credit": 0.0} # Revert crypto asset decrease
                    ],
                    crypto_transaction=db_crypto_transaction
                )
                await db.commit()
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=crypto_response["message"])
            
            db_crypto_transaction.status = "awaiting_confirmation"
            db_crypto_transaction.transaction_hash = crypto_response.get("transaction_hash")
            await db.commit()
            await db.refresh(db_crypto_transaction)

        elif request.status == "rejected":
            # Revert balance (already deducted optimistically)
            user_crypto_wallet.balance += total_amount
            db_crypto_transaction.status = "rejected"
            # Optionally add rejection reason to metadata_json for CryptoTransaction if it has one

            # Create reversal ledger entry
            await ledger_service.create_journal_entry(
                description=f"Admin Reject Crypto Withdrawal for user {db_crypto_transaction.user_id}",
                ledger_entries_data=[
                    {"account_name": "Customer Crypto Balances (Liability)", "debit": 0.0, "credit": total_amount}, # Revert liability decrease
                    {"account_name": "Crypto Hot Wallet (Asset)", "debit": total_amount, "credit": 0.0} # Revert crypto asset decrease
                ],
                crypto_transaction=db_crypto_transaction
            )
            await db.commit()
            await db.refresh(db_crypto_transaction)
        
        return db_crypto_transaction
    finally:
        await db.close()


@router.post("/withdrawals/bank/initiate", response_model=PaymentResponse)
async def initiate_bank_withdrawal_admin(
    request: BankWithdrawalInitiateRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    ledger_service: LedgerService = Depends(get_ledger_service),
    bank_service: BankService = Depends(get_bank_service)
):
    """
    Admin initiates a bank withdrawal for revenue payout.
    """
    try:
        # Simulate bank withdrawal
        bank_response = await bank_service.initiate_withdrawal(
            amount=request.amount,
            currency=request.currency,
            bank_name=request.bank_name,
            account_name=request.account_name,
            account_number=request.account_number,
            swift_code=request.swift_code,
            user_id=admin_user.id # Admin is initiating, so linking to admin user
        )

        if bank_response["status"] == "failed":
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=bank_response["message"])

        # Create Payment record
        new_payment = Payment(
            user_id=admin_user.id, # Initiated by admin
            amount=request.amount,
            currency=request.currency,
            type="withdrawal",
            processor="bank",
            status="pending", # Awaiting bank confirmation
            processor_transaction_id=bank_response.get("processor_transaction_id"),
            metadata_json=json.dumps({
                "bank_name": request.bank_name,
                "account_name": request.account_name,
                "account_number": request.account_number,
                "swift_code": request.swift_code,
                "notes": request.notes,
                "initiated_by_admin_id": admin_user.id
            })
        )
        db.add(new_payment)
        await db.commit()
        await db.refresh(new_payment)

        result = await db.execute(select(Wallet).filter(Wallet.user_id == admin_user.id))
        admin_wallet = result.scalars().first()
        if not admin_wallet:
            admin_wallet = Wallet(user_id=admin_user.id, balance=0.0, currency=request.currency)
            db.add(admin_wallet)
            await db.commit()
            await db.refresh(admin_wallet)

        # Create internal Transaction record for ledger tracking
        new_transaction = Transaction(
            user_id=admin_user.id,
            wallet_id=admin_wallet.id,
            amount=request.amount,
            currency=request.currency,
            type="admin_bank_withdrawal_initiate",
            status="pending",
            metadata_json=json.dumps({"payment_id": new_payment.id, "notes": request.notes})
        )
        db.add(new_transaction)
        await db.commit()
        await db.refresh(new_transaction)

        # Create ledger entries
        await ledger_service.create_journal_entry(
            description=f"Admin initiated bank withdrawal to {request.account_name} ({request.account_number})",
            ledger_entries_data=[
                {"account_name": "Revenue Payout (Expense)", "debit": request.amount, "credit": 0.0}, # Debit revenue/expense account
                {"account_name": "Cash (External Bank)", "debit": 0.0, "credit": request.amount} # Credit external bank cash
            ],
            payment=new_payment,
            transaction=new_transaction
        )
        
        return new_payment
    finally:
        await db.close()


@router.post("/withdrawals/momo/initiate", response_model=PaymentResponse)
async def initiate_momo_withdrawal_admin(
    request: MomoWithdrawalInitiateRequest,
    admin_user: User = Depends(get_admin_user),
    payout_service: PayoutService = Depends(get_payout_service),
):
    """
    Admin initiates a Mobile Money withdrawal for revenue payout.
    """
    return await payout_service.initiate_momo_payout(
        current_user=admin_user,
        amount=request.amount,
        account_number=request.phone_number,
        currency=request.currency,
        network=request.network,
        notes=request.notes,
        requested_user_id=admin_user.id,
    )


@router.post("/withdrawals/crypto/initiate", response_model=CryptoTransactionResponse)
async def initiate_crypto_withdrawal_admin(
    request: AdminCryptoWithdrawalInitiateRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    ledger_service: LedgerService = Depends(get_ledger_service)
):
    """
    Admin initiates a cryptocurrency withdrawal for revenue payout.
    """
    try:
        # Simulate crypto withdrawal
        crypto_response = await crypto_service.initiate_withdrawal(
            from_address="OUR_HOT_WALLET_ADDRESS", # Funds come from our hot wallet
            to_address=request.to_address,
            coin_type=request.coin_type,
            amount=request.amount
        )

        if crypto_response["status"] == "failed":
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=crypto_response["message"])

        # Create CryptoTransaction record
        new_crypto_transaction = CryptoTransaction(
            user_id=admin_user.id, # Initiated by admin
            crypto_wallet_id=None, # Not from a user's specific crypto wallet, but from exchange/hot wallet
            amount=request.amount,
            fee=request.fee,
            coin_type=request.coin_type,
            to_address=request.to_address,
            transaction_hash=crypto_response.get("transaction_hash"),
            type="withdrawal",
            status="awaiting_confirmation", # Awaiting blockchain confirmation
            metadata_json=json.dumps({
                "notes": request.notes,
                "currency_equivalent": request.currency, # For tracking equivalent fiat value
                "initiated_by_admin_id": admin_user.id
            })
        )
        db.add(new_crypto_transaction)
        await db.commit()
        await db.refresh(new_crypto_transaction)

        # Create ledger entries
        await ledger_service.create_journal_entry(
            description=f"Admin initiated crypto withdrawal ({request.coin_type}) to {request.to_address}",
            ledger_entries_data=[
                {"account_name": "Revenue Payout (Expense)", "debit": request.amount + request.fee, "credit": 0.0}, # Debit revenue/expense
                {"account_name": "Crypto Hot Wallet (Asset)", "debit": 0.0, "credit": request.amount + request.fee} # Credit crypto hot wallet
            ],
            crypto_transaction=new_crypto_transaction
        )

        return new_crypto_transaction
    finally:
        await db.close()
