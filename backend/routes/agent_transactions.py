from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, or_, select
from typing import Optional, List
from datetime import datetime, timezone
import json
from pydantic import BaseModel

from backend.database import get_db
from backend.models import User, Agent, Wallet, Transaction, Loan
from backend.schemas.transaction import TransactionResponse
from backend.schemas.agent import AgentCashDepositRequest, AgentCashWithdrawalRequest
from backend.dependencies.auth import get_current_user
from backend.services.ledger_service import LedgerService, get_ledger_service
from backend.services.transaction_engine import TransactionEngine, get_transaction_engine
from backend.services.commission_service import record_commission
from backend.services import loan_service
from backend.core.config import settings
from backend.core.transaction_types import TransactionType
from utils.network import normalize_ghana_number

router = APIRouter(
    prefix="/agent-transactions",
    tags=["Agent Transactions"]
)

RECOVERABLE_AGENT_STATUSES = {"pending", "failed"}
RECOVERABLE_AGENT_TYPES = {TransactionType.AGENT_DEPOSIT, TransactionType.AGENT_WITHDRAWAL}


class AgentWalletStructureResponse(BaseModel):
    agent_id: int
    agent_float_balance: float
    agent_commission_balance: float
    agent_transaction_count: int


def _parse_metadata_json(raw_metadata: Optional[str]) -> dict:
    if not raw_metadata:
        return {}
    try:
        parsed = json.loads(raw_metadata)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _normalize_transaction_for_response(tx: Transaction) -> Transaction:
    """
    Normalizes nullable legacy fields so response-model validation remains stable.
    """
    if tx.commission_earned is None:
        tx.commission_earned = 0.0
    return tx


def _normalize_transactions_for_response(rows: List[Transaction]) -> List[Transaction]:
    return [_normalize_transaction_for_response(tx) for tx in rows]


async def _resolve_customer_user_id(
    db: AsyncSession,
    user_id: Optional[int],
    customer_email: Optional[str],
    customer_phone: Optional[str],
) -> int:
    if user_id:
        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalars().first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
        return user.id

    if customer_email:
        normalized_email = str(customer_email).strip().lower()
        result = await db.execute(select(User).filter(func.lower(User.email) == normalized_email))
        user = result.scalars().first()
        if user:
            return user.id

    if customer_phone:
        normalized_phone = normalize_ghana_number(str(customer_phone).strip())
        phone_candidates = {normalized_phone}
        digits_only = "".join(ch for ch in normalized_phone if ch.isdigit())

        # Accept local, 233, and +233 variants for resilient customer matching.
        if digits_only:
            if digits_only.startswith("0") and len(digits_only) >= 10:
                intl = digits_only[1:]
                phone_candidates.add(f"233{intl}")
                phone_candidates.add(f"+233{intl}")
            elif digits_only.startswith("233") and len(digits_only) >= 12:
                local = f"0{digits_only[3:]}"
                phone_candidates.add(local)
                phone_candidates.add(f"+{digits_only}")

        sanitized_candidates = [candidate for candidate in phone_candidates if candidate]
        result = await db.execute(
            select(User).filter(
                or_(
                    User.phone_number.in_(sanitized_candidates),
                    User.momo_number.in_(sanitized_candidates),
                )
            )
        )
        user = result.scalars().first()
        if user:
            return user.id

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Provide a valid customer identifier (user_id, customer_email, or customer_phone).",
    )

async def get_current_active_agent(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Agent:
    result = await db.execute(select(Agent).filter(Agent.user_id == current_user.id))
    agent = result.scalars().first()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not registered as an agent"
        )

    if agent.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent account is not active"
        )
    return agent

@router.post("/cash-deposit", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def agent_cash_deposit(
    request: AgentCashDepositRequest,
    db: AsyncSession = Depends(get_db),
    agent: Agent = Depends(get_current_active_agent),
    transaction_engine: TransactionEngine = Depends(get_transaction_engine),
):
    if request.amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount must be positive.")

    gross_amount = round(float(request.amount), 2)
    topup_fee_rate = float(getattr(request, "topup_fee_rate", 0.0) or 0.0)
    topup_fee = round(gross_amount * topup_fee_rate, 2)
    credited_amount = round(gross_amount - topup_fee, 2)
    if credited_amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Top-up fee leaves no credit to apply.")

    customer_user_id = await _resolve_customer_user_id(
        db=db,
        user_id=request.user_id,
        customer_email=request.customer_email,
        customer_phone=request.customer_phone,
    )
    result = await db.execute(select(User).filter(User.id == customer_user_id))
    customer_user = result.scalars().first()
    if not customer_user or not customer_user.is_active or not customer_user.is_verified:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer account not found.")

    commission_earned = round(gross_amount * float(agent.commission_rate or 0.0), 2)

    try:
        transaction = await transaction_engine.process_transaction(
            user_id=customer_user_id,
            transaction_type=TransactionType.AGENT_DEPOSIT,
            amount=credited_amount,
            agent_id=agent.id,
            metadata={
                "customer_user_id": customer_user_id,
                "customer_email": request.customer_email,
                "customer_phone": request.customer_phone,
                "gross_amount": gross_amount,
                "topup_fee_rate": topup_fee_rate,
                "topup_fee": topup_fee,
                "net_amount": credited_amount,
                "fee": topup_fee,
                "commission": commission_earned,
                "funding_source": "agent_float",
                "transaction_kind": "user_topup",
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return transaction

@router.post("/cash-withdrawal", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def agent_cash_withdrawal(
    request: AgentCashWithdrawalRequest,
    db: AsyncSession = Depends(get_db),
    agent: Agent = Depends(get_current_active_agent),
    transaction_engine: TransactionEngine = Depends(get_transaction_engine)
):
    if request.amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount must be positive.")

    customer_user_id = await _resolve_customer_user_id(
        db=db,
        user_id=request.user_id,
        customer_email=request.customer_email,
        customer_phone=request.customer_phone,
    )

    # 1. Calculate Commission
    commission_earned = request.amount * agent.commission_rate
    
    # 2. Loan Repayment Logic (Shared)
    result = await db.execute(select(Loan).filter(
        Loan.agent_id == agent.id,
        Loan.status.in_(loan_service.OPEN_LOAN_STATUSES),
        Loan.outstanding_balance > 0
    ))
    active_loan = result.scalars().first()
    
    loan_repayment_amount = 0.0
    if active_loan:
        repayment_percentage = settings.LOAN_REPAYMENT_PERCENTAGE
        loan_repayment_amount = min(commission_earned * repayment_percentage, active_loan.outstanding_balance)
        
        active_loan.outstanding_balance -= loan_repayment_amount
        if active_loan.outstanding_balance <= 0:
            active_loan.outstanding_balance = 0
            active_loan.status = "repaid"
            active_loan.repayment_date = datetime.now()
        elif active_loan.repayment_due_date and datetime.now() > active_loan.repayment_due_date:
            active_loan.status = "overdue"
        db.add(active_loan)
        await loan_service.sync_wallet_loan_balance(
            db,
            agent.user_id,
            active_agent_id=agent.id,
        )

    # 3. Process Transaction
    # Withdrawal Fee logic:
    # Usually customer pays a fee.
    # e.g., Request 100. Fee 2. Wallet deducted 102. Agent gives 100.
    # Metadata "fee" is handled by engine.
    withdrawal_fee = request.amount * 0.01 # 1% fee for example, should be from settings
    
    try:
        transaction = await transaction_engine.process_transaction(
            user_id=customer_user_id,
            transaction_type=TransactionType.AGENT_WITHDRAWAL,
            amount=request.amount,
            agent_id=agent.id,
            metadata={
                "commission": commission_earned,
                "fee": withdrawal_fee,
                "pin_verified": True,
                "customer_email": request.customer_email,
                "customer_phone": request.customer_phone,
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if loan_repayment_amount > 0:
        agent.commission_balance -= loan_repayment_amount
        db.add(agent)
        await record_commission(
            db,
            agent_id=agent.id,
            user_id=customer_user_id,
            amount=-loan_repayment_amount,
            currency=request.currency,
            commission_type="LOAN_REPAYMENT_OFFSET",
            status="offset",
            transaction=transaction,
            metadata={"source": "agent_cash_withdrawal_auto_repayment"},
        )
        
        await transaction_engine.ledger_service.create_journal_entry(
            description=f"Auto Loan Repayment from Commission (Agent {agent.id})",
            ledger_entries_data=[
                {"account_name": "Commissions Payable (Liability)", "debit": loan_repayment_amount},
                {"account_name": "Loan Principal (Asset)", "credit": loan_repayment_amount}
            ],
            transaction=transaction
        )

    return transaction


@router.get("/me/wallet-structure", response_model=AgentWalletStructureResponse, status_code=status.HTTP_200_OK)
async def get_agent_wallet_structure(
    db: AsyncSession = Depends(get_db),
    agent: Agent = Depends(get_current_active_agent),
):
    result = await db.execute(select(Transaction).filter(Transaction.agent_id == agent.id))
    tx_count = len(result.scalars().all())
    return AgentWalletStructureResponse(
        agent_id=agent.id,
        agent_float_balance=agent.float_balance,
        agent_commission_balance=agent.commission_balance,
        agent_transaction_count=tx_count,
    )


@router.get("/me/history", response_model=List[TransactionResponse], status_code=status.HTTP_200_OK)
async def get_agent_transaction_history(
    db: AsyncSession = Depends(get_db),
    agent: Agent = Depends(get_current_active_agent),
):
    result = await db.execute(
        select(Transaction)
        .filter(Transaction.agent_id == agent.id)
        .order_by(Transaction.timestamp.desc())
    )
    return _normalize_transactions_for_response(result.scalars().all())


@router.get("/me/recovery-candidates", response_model=List[TransactionResponse], status_code=status.HTTP_200_OK)
async def get_agent_recovery_candidates(
    db: AsyncSession = Depends(get_db),
    agent: Agent = Depends(get_current_active_agent),
):
    """
    Lists agent-owned cash transactions that are eligible for recovery.
    """
    result = await db.execute(
        select(Transaction)
        .filter(
            Transaction.agent_id == agent.id,
            Transaction.type.in_(tuple(RECOVERABLE_AGENT_TYPES)),
            func.lower(Transaction.status).in_(tuple(RECOVERABLE_AGENT_STATUSES)),
        )
        .order_by(Transaction.timestamp.desc())
    )
    return _normalize_transactions_for_response(result.scalars().all())


@router.post("/me/recover/{transaction_id}", response_model=TransactionResponse, status_code=status.HTTP_200_OK)
async def recover_agent_transaction(
    transaction_id: int,
    db: AsyncSession = Depends(get_db),
    agent: Agent = Depends(get_current_active_agent),
    transaction_engine: TransactionEngine = Depends(get_transaction_engine),
):
    """
    Recovers a failed/pending agent cash transaction.
    - pending/failed: replays a fresh transaction with original payload, preserving
      validation/limits, then marks original as recovered.
    """
    result = await db.execute(
        select(Transaction).filter(
            Transaction.id == transaction_id,
            Transaction.agent_id == agent.id,
        )
    )
    source_tx = result.scalars().first()

    if not source_tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent transaction not found.")

    if source_tx.type not in RECOVERABLE_AGENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only agent cash deposit/withdrawal transactions can be recovered.",
        )

    source_metadata = _parse_metadata_json(source_tx.metadata_json)

    # Idempotent recovery: return previously created recovery transaction when available.
    existing_recovery_id = source_metadata.get("recovery_created_transaction_id")
    if existing_recovery_id:
        try:
            recovery_id = int(existing_recovery_id)
        except (TypeError, ValueError):
            recovery_id = 0
        if recovery_id > 0:
            existing_result = await db.execute(
                select(Transaction).filter(
                    Transaction.id == recovery_id,
                    Transaction.agent_id == agent.id,
                )
            )
            existing_recovery = existing_result.scalars().first()
            if existing_recovery:
                return _normalize_transaction_for_response(existing_recovery)

    status_normalized = str(source_tx.status or "").strip().lower()
    if status_normalized not in RECOVERABLE_AGENT_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transaction cannot be recovered from status '{source_tx.status}'.",
        )

    # Replay as a new transaction (for both pending and failed source statuses).
    replay_metadata = dict(source_metadata)
    replay_metadata["pin_verified"] = bool(replay_metadata.get("pin_verified", True))
    replay_metadata["recovered_from_transaction_id"] = source_tx.id
    replay_metadata["recovery_attempted_at"] = datetime.now(timezone.utc).isoformat()

    try:
        recovered_tx = await transaction_engine.process_transaction(
            user_id=source_tx.user_id,
            transaction_type=source_tx.type,
            amount=float(source_tx.amount),
            agent_id=source_tx.agent_id,
            metadata=replay_metadata,
        )
    except ValueError as exc:
        # Preserve failure metadata for future debugging/retry.
        source_metadata["last_recovery_error"] = str(exc)
        source_metadata["last_recovery_attempt_at"] = datetime.now(timezone.utc).isoformat()
        source_tx.metadata_json = json.dumps(source_metadata)
        db.add(source_tx)
        await db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    source_metadata["recovery_created_transaction_id"] = recovered_tx.id
    source_metadata["recovered_at"] = datetime.now(timezone.utc).isoformat()
    source_tx.status = "recovered"
    source_tx.metadata_json = json.dumps(source_metadata)
    db.add(source_tx)
    await db.commit()

    return _normalize_transaction_for_response(recovered_tx)
