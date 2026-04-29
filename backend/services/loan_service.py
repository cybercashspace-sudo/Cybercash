from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from datetime import datetime, timedelta

from backend.core.transaction_types import TransactionType
from backend.services.ledger_service import LedgerService
from backend.services.transaction_engine import TransactionEngine

from .. import models, schemas
from ..core.config import settings
from ..schemas.loan_application import LoanApplicationCreate # Added import
from ..schemas.loan_admin import LoanOverviewResponse, AgentCreditProfileResponse # Added import


USER_LOAN_PERIODS = (1, 7, 14, 30)
AGENT_ONLY_LOAN_PERIODS = (60, 90)
BASE_LOAN_FEE_PERCENTAGE = 15.0
LATE_LOAN_FEE_PERCENTAGE = 20.0
LATE_FEE_GRACE_HOURS = 24
OPEN_LOAN_STATUSES = ("active", "overdue")


def _money(value: float | int | None) -> float:
    return round(float(value or 0.0), 2)


def _loan_owner_filter(model, user_id: int, active_agent_id: int | None = None):
    filters = [model.user_id == user_id]
    if active_agent_id:
        filters.append(and_(model.user_id.is_(None), model.agent_id == active_agent_id))
    return or_(*filters) if len(filters) > 1 else filters[0]


def _loan_total_fee_amount(loan: models.Loan) -> float:
    return _money(float(loan.base_fee_amount or 0.0) + float(loan.late_fee_amount or 0.0))


def _loan_total_due_amount(loan: models.Loan) -> float:
    return _money(float(loan.amount or 0.0) + _loan_total_fee_amount(loan))


async def get_active_agent_for_user(db: AsyncSession, user_id: int) -> models.Agent | None:
    result = await db.execute(
        select(models.Agent).filter(
            models.Agent.user_id == user_id,
            models.Agent.status == "active",
        )
    )
    return result.scalars().first()


async def get_allowed_periods_for_user(db: AsyncSession, user: models.User) -> tuple[tuple[int, ...], models.Agent | None]:
    active_agent = await get_active_agent_for_user(db, user.id)
    allowed_periods = USER_LOAN_PERIODS
    if active_agent:
        allowed_periods = USER_LOAN_PERIODS + AGENT_ONLY_LOAN_PERIODS
    return allowed_periods, active_agent


def get_allowed_periods_text(allowed_periods: tuple[int, ...] | list[int]) -> str:
    labels = []
    for period in allowed_periods:
        labels.append(f"{int(period)} day" if int(period) == 1 else f"{int(period)} days")
    return ", ".join(labels)


async def get_loan_policy_for_user(db: AsyncSession, user: models.User) -> dict:
    allowed_periods, active_agent = await get_allowed_periods_for_user(db, user)
    return {
        "allowed_periods": [int(period) for period in allowed_periods],
        "is_agent_eligible": bool(active_agent),
        "auto_deduction_enabled": True,
        "base_fee_percentage": BASE_LOAN_FEE_PERCENTAGE,
        "late_fee_percentage": LATE_LOAN_FEE_PERCENTAGE,
        "late_fee_grace_hours": LATE_FEE_GRACE_HOURS,
        "period_help_text": (
            "Choose a repayment period that matches your account. "
            f"Available periods: {get_allowed_periods_text(allowed_periods)}."
        ),
        "fee_help_text": (
            f"Each loan adds a {BASE_LOAN_FEE_PERCENTAGE:.0f}% service fee upfront. "
            f"If a balance is still unpaid {LATE_FEE_GRACE_HOURS} hours after the due date, "
            f"a one-time {LATE_LOAN_FEE_PERCENTAGE:.0f}% overdue fee is added on the original loan amount."
        ),
    }


async def get_open_loan_for_user(
    db: AsyncSession,
    user_id: int,
    active_agent_id: int | None = None,
) -> models.Loan | None:
    result = await db.execute(
        select(models.Loan)
        .filter(
            _loan_owner_filter(models.Loan, user_id, active_agent_id),
            models.Loan.status.in_(OPEN_LOAN_STATUSES),
        )
        .order_by(models.Loan.disbursement_date.desc(), models.Loan.id.desc())
    )
    return result.scalars().first()


async def sync_wallet_loan_balance(
    db: AsyncSession,
    user_id: int,
    *,
    wallet: models.Wallet | None = None,
    active_agent_id: int | None = None,
) -> models.Wallet:
    if wallet is None:
        result = await db.execute(select(models.Wallet).filter(models.Wallet.user_id == user_id))
        wallet = result.scalars().first()
        if wallet is None:
            wallet = models.Wallet(user_id=user_id, currency="GHS", balance=0.0)
            db.add(wallet)
            await db.flush()

    owner_filter = _loan_owner_filter(models.Loan, user_id, active_agent_id)
    result = await db.execute(
        select(models.Loan.outstanding_balance).filter(
            owner_filter,
            models.Loan.status.in_(OPEN_LOAN_STATUSES),
        )
    )
    outstanding_values = result.scalars().all()
    wallet.loan_balance = _money(sum(float(value or 0.0) for value in outstanding_values))
    db.add(wallet)
    return wallet


async def apply_due_loan_updates(db: AsyncSession, loan: models.Loan) -> bool:
    if not loan or str(loan.status or "").strip().lower() == "repaid":
        return False

    now = datetime.now()
    changed = False
    due_date = loan.repayment_due_date
    if due_date is None:
        return False

    if due_date.tzinfo is not None:
        now = datetime.now(due_date.tzinfo)

    if loan.outstanding_balance > 0 and now > due_date and str(loan.status or "").strip().lower() != "overdue":
        loan.status = "overdue"
        changed = True

    late_fee_amount = _money(loan.late_fee_amount)
    late_fee_due_at = due_date + timedelta(hours=LATE_FEE_GRACE_HOURS)
    if loan.outstanding_balance > 0 and now >= late_fee_due_at and late_fee_amount <= 0.0:
        late_fee_amount = _money(float(loan.amount or 0.0) * (float(loan.late_fee_percentage or LATE_LOAN_FEE_PERCENTAGE) / 100.0))
        if late_fee_amount > 0:
            loan.late_fee_amount = late_fee_amount
            loan.late_fee_applied_at = now
            loan.outstanding_balance = _money(float(loan.outstanding_balance or 0.0) + late_fee_amount)
            loan.status = "overdue"
            changed = True

    if changed:
        db.add(loan)
    return changed


async def _fetch_user_wallet_and_agent(
    db: AsyncSession,
    user_id: int,
) -> tuple[models.User | None, models.Wallet | None, models.Agent | None]:
    user_result = await db.execute(select(models.User).filter(models.User.id == user_id))
    user = user_result.scalars().first()

    wallet_result = await db.execute(select(models.Wallet).filter(models.Wallet.user_id == user_id))
    wallet = wallet_result.scalars().first()
    if wallet is None:
        wallet = models.Wallet(user_id=user_id, currency="GHS", balance=0.0)
        db.add(wallet)
        await db.flush()

    active_agent = await get_active_agent_for_user(db, user_id)
    return user, wallet, active_agent


async def repay_loan_for_user(
    db: AsyncSession,
    user_id: int,
    loan_id: int,
    repayment_amount: float,
    *,
    trigger: str = "manual",
) -> models.Loan | None:
    user, wallet, active_agent = await _fetch_user_wallet_and_agent(db, user_id)
    if user is None or wallet is None:
        return None

    result = await db.execute(select(models.Loan).filter(models.Loan.id == loan_id))
    db_loan = result.scalars().first()
    if not db_loan or str(db_loan.status or "").strip().lower() == "repaid":
        return None

    owner_filter = _loan_owner_filter(models.Loan, user_id, active_agent.id if active_agent else None)
    owned_result = await db.execute(select(models.Loan.id).filter(owner_filter, models.Loan.id == loan_id))
    if owned_result.scalar_one_or_none() is None:
        return None

    if wallet.is_frozen:
        raise ValueError("Wallet is frozen.")

    await apply_due_loan_updates(db, db_loan)

    if str(trigger or "").strip().lower() == "manual" and not bool(getattr(db_loan, "manual_repayment_allowed", True)):
        raise ValueError(
            str(getattr(db_loan, "manual_repayment_message", "") or "").strip()
            or "Manual repayment is unavailable for this loan right now."
        )

    capped_amount = min(_money(repayment_amount), _money(wallet.balance), _money(db_loan.outstanding_balance))
    if capped_amount <= 0:
        raise ValueError("No repayable loan balance is available from your wallet right now.")

    total_fee = _loan_total_fee_amount(db_loan)
    total_due = _loan_total_due_amount(db_loan)
    paid_so_far = max(0.0, _money(total_due - float(db_loan.outstanding_balance or 0.0)))
    fee_paid_so_far = min(total_fee, paid_so_far)
    remaining_fee = max(0.0, _money(total_fee - fee_paid_so_far))
    fee_component = min(capped_amount, remaining_fee)

    ledger_service = LedgerService(db)
    transaction_engine = TransactionEngine(db, ledger_service)
    await transaction_engine.process_transaction(
        user_id=user.id,
        transaction_type=TransactionType.LOAN_REPAY,
        amount=capped_amount,
        agent_id=db_loan.agent_id,
        metadata={
            "loan_id": db_loan.id,
            "application_id": db_loan.application_id,
            "interest_amount": fee_component,
            "repayment_trigger": trigger,
        },
    )

    db_loan.outstanding_balance = _money(float(db_loan.outstanding_balance or 0.0) - capped_amount)
    if db_loan.outstanding_balance <= 0:
        db_loan.outstanding_balance = 0.0
        db_loan.status = "repaid"
        db_loan.repayment_date = datetime.now()
    elif db_loan.repayment_due_date and datetime.now() > db_loan.repayment_due_date:
        db_loan.status = "overdue"
    else:
        db_loan.status = "active"

    db.add(db_loan)
    await sync_wallet_loan_balance(
        db,
        user.id,
        wallet=wallet,
        active_agent_id=active_agent.id if active_agent else None,
    )
    await db.commit()
    await db.refresh(db_loan)
    return db_loan


async def run_loan_maintenance_for_user(
    db: AsyncSession,
    user_id: int,
    *,
    allow_auto_deduction: bool = False,
) -> dict:
    user, wallet, active_agent = await _fetch_user_wallet_and_agent(db, user_id)
    if user is None or wallet is None:
        return {"loan": None, "wallet": None, "auto_deducted_amount": 0.0, "late_fee_applied": False}

    active_agent_id = active_agent.id if active_agent else None
    loan = await get_open_loan_for_user(db, user.id, active_agent_id)
    if loan is None:
        await sync_wallet_loan_balance(db, user.id, wallet=wallet, active_agent_id=active_agent_id)
        await db.commit()
        await db.refresh(wallet)
        return {"loan": None, "wallet": wallet, "auto_deducted_amount": 0.0, "late_fee_applied": False}

    late_fee_applied = await apply_due_loan_updates(db, loan)

    auto_deducted_amount = 0.0
    if allow_auto_deduction and float(wallet.balance or 0.0) > 0.0 and float(loan.outstanding_balance or 0.0) > 0.0:
        payable_amount = min(_money(wallet.balance), _money(loan.outstanding_balance))
        if payable_amount > 0:
            loan = await repay_loan_for_user(
                db,
                user.id,
                loan.id,
                payable_amount,
                trigger="auto_wallet_sweep",
            )
            auto_deducted_amount = payable_amount
            result = await db.execute(select(models.Wallet).filter(models.Wallet.user_id == user.id))
            wallet = result.scalars().first()
            return {
                "loan": loan,
                "wallet": wallet,
                "auto_deducted_amount": auto_deducted_amount,
                "late_fee_applied": late_fee_applied,
            }

    await sync_wallet_loan_balance(db, user.id, wallet=wallet, active_agent_id=active_agent_id)
    await db.commit()
    await db.refresh(loan)
    await db.refresh(wallet)
    return {
        "loan": loan,
        "wallet": wallet,
        "auto_deducted_amount": auto_deducted_amount,
        "late_fee_applied": late_fee_applied,
    }


async def create_self_service_loan(
    db: AsyncSession,
    user: models.User,
    application: LoanApplicationCreate,
    transaction_metadata: dict | None = None,
) -> models.LoanApplication:
    amount = _money(application.amount)
    if amount <= 0:
        raise ValueError("Loan amount must be greater than zero.")

    allowed_periods, active_agent = await get_allowed_periods_for_user(db, user)
    duration = int(application.repayment_duration or 0)
    if duration not in allowed_periods:
        raise ValueError(
            "Unsupported repayment period selected. "
            f"Choose one of: {get_allowed_periods_text(allowed_periods)}."
        )

    if active_agent and active_agent.is_borrowing_frozen:
        raise ValueError("Loan access is temporarily paused for this agent profile.")

    existing_loan = await get_open_loan_for_user(db, user.id, active_agent.id if active_agent else None)
    if existing_loan:
        raise ValueError("You already have an active loan. Repay it before requesting another one.")

    result = await db.execute(
        select(models.LoanApplication).filter(
            _loan_owner_filter(models.LoanApplication, user.id, active_agent.id if active_agent else None),
            models.LoanApplication.status.in_(["pending_admin_approval", "approved"]),
        )
    )
    pending_application = result.scalars().first()
    if pending_application:
        raise ValueError("You already have a loan request being processed. Complete that loan first.")

    base_fee_amount = _money(amount * (BASE_LOAN_FEE_PERCENTAGE / 100.0))
    total_due = _money(amount + base_fee_amount)
    now = datetime.now()
    repayment_due_date = now + timedelta(days=duration)
    risk_score = await calculate_credit_score(db, active_agent.id) if active_agent else 75

    db_application = models.LoanApplication(
        user_id=user.id,
        agent_id=active_agent.id if active_agent else None,
        amount=amount,
        repayment_duration=duration,
        purpose=application.purpose,
        approved_amount=amount,
        fee_percentage=BASE_LOAN_FEE_PERCENTAGE,
        offered_repayment_duration=duration,
        status="disbursed",
        approved_date=now,
        reviewed_at=now,
        review_note="Instant approval under the current wallet loan policy.",
        risk_score=risk_score,
    )
    db.add(db_application)
    await db.flush()

    db_loan = models.Loan(
        user_id=user.id,
        agent_id=active_agent.id if active_agent else None,
        application_id=db_application.id,
        amount=amount,
        repayment_duration=duration,
        base_fee_percentage=BASE_LOAN_FEE_PERCENTAGE,
        base_fee_amount=base_fee_amount,
        late_fee_percentage=LATE_LOAN_FEE_PERCENTAGE,
        late_fee_amount=0.0,
        outstanding_balance=total_due,
        repayment_due_date=repayment_due_date,
        status="active",
    )
    db.add(db_loan)
    await db.flush()

    ledger_service = LedgerService(db)
    transaction_engine = TransactionEngine(db, ledger_service)
    loan_metadata = dict(transaction_metadata or {})
    loan_metadata.update(
        {
            "loan_id": db_loan.id,
            "application_id": db_application.id,
            "fee_percentage": BASE_LOAN_FEE_PERCENTAGE,
            "base_fee_amount": base_fee_amount,
            "wallet_loan_balance_increase": total_due,
            "repayment_due_date": repayment_due_date.isoformat(),
            "repayment_duration": duration,
        }
    )
    await transaction_engine.process_transaction(
        user_id=user.id,
        transaction_type=TransactionType.LOAN_DISBURSE,
        amount=amount,
        agent_id=active_agent.id if active_agent else None,
        metadata=loan_metadata,
    )

    result = await db.execute(select(models.Wallet).filter(models.Wallet.user_id == user.id))
    wallet = result.scalars().first()
    if wallet:
        await sync_wallet_loan_balance(
            db,
            user.id,
            wallet=wallet,
            active_agent_id=active_agent.id if active_agent else None,
        )
        await db.commit()

    await db.refresh(db_application)
    return db_application


async def _get_agent_transactions_data(db: AsyncSession, agent_id: int, days_back: int = 30):
    """Helper to fetch recent transaction data for scoring."""
    start_date = datetime.now() - timedelta(days=days_back)
    
    result = await db.execute(
        select(models.Transaction).filter(
            and_(
                models.Transaction.agent_id == agent_id,
                models.Transaction.timestamp >= start_date,
                models.Transaction.status == "completed"
            )
        )
    )
    transactions = result.scalars().all()
    
    return transactions

def _calculate_volume_score(transactions: list) -> float:
    """Calculate Volume Score based on transaction count and growth."""
    daily_counts = {}
    for tx in transactions:
        date_key = tx.timestamp.date()
        daily_counts[date_key] = daily_counts.get(date_key, 0) + 1
    
    total_tx_count = len(transactions)
    
    # Simple growth: compare first half vs second half of the period
    mid_point_date = datetime.now() - timedelta(days=len(daily_counts.keys()) // 2)
    first_half_tx = [tx for tx in transactions if tx.timestamp.date() < mid_point_date.date()]
    second_half_tx = [tx for tx in transactions if tx.timestamp.date() >= mid_point_date.date()]

    growth_factor = 1.0
    if len(first_half_tx) > 0:
        growth_factor = len(second_half_tx) / len(first_half_tx)
    
    # Example scoring: more transactions, better score; positive growth, better score
    score = (total_tx_count / 100.0) * 50 + (growth_factor * 10) # Max 50 for volume, 10 for growth
    return min(100.0, max(0.0, score))


def _calculate_consistency_score(transactions: list) -> float:
    """Calculate Consistency Score based on cash-in vs cash-out balance and average size."""
    cash_in = sum(
        tx.amount
        for tx in transactions
        if tx.type in [TransactionType.AGENT_DEPOSIT, "cash_deposit", "topup"]
    )
    cash_out = sum(
        tx.amount
        for tx in transactions
        if tx.type in [TransactionType.AGENT_WITHDRAWAL, TransactionType.AIRTIME, "cash_withdrawal", "airtime_resale"]
    )
    
    balance_ratio_score = 50.0 # Default
    if (cash_in + cash_out) > 0:
        if cash_in > cash_out:
            balance_ratio_score = 50 + min(50, (cash_in - cash_out) / (cash_in + cash_out) * 100)
        else:
            balance_ratio_score = 50 - min(50, (cash_out - cash_in) / (cash_in + cash_out) * 100)
            
    avg_tx_size = sum(tx.amount for tx in transactions) / len(transactions) if transactions else 0
    avg_tx_size_score = min(50.0, avg_tx_size / 100.0 * 20) # Max 50 for average size

    return min(100.0, max(0.0, (balance_ratio_score + avg_tx_size_score) / 2))

async def _calculate_repayment_score(db: AsyncSession, agent_id: int) -> float:
    """Calculate Repayment Score based on previous loan repayment history."""
    result = await db.execute(select(models.Loan).filter(models.Loan.agent_id == agent_id))
    loans = result.scalars().all()
    
    if not loans:
        return 100.0 # Perfect score if no history

    repaid_on_time = 0
    total_repaid = 0
    for loan in loans:
        if loan.status == "repaid":
            total_repaid += 1
            if loan.repayment_date and loan.repayment_date <= loan.repayment_due_date:
                repaid_on_time += 1
    
    if total_repaid == 0:
        return 50.0 # Neutral score if no loans fully repaid yet

    score = (repaid_on_time / total_repaid) * 100.0
    return min(100.0, max(0.0, score))

async def _calculate_trust_score(db: AsyncSession, agent: models.Agent, transactions: list) -> float:
    """Calculate Trust Score based on account age, KYC, device/location consistency."""
    result = await db.execute(select(models.User).filter(models.User.id == agent.user_id))
    user = result.scalars().first()
    
    account_age_days = (datetime.now() - user.created_at).days if user else 0
    account_age_score = min(50.0, account_age_days / 365 * 20) # Max 50 for 1 year old account

    kyc_score = 50.0 if user and user.is_verified else 0.0 # Max 50 for KYC verified

    # For now, device/location consistency are conceptual
    # In a real system, transaction metadata would include device IDs and precise locations
    # and historical analysis would be performed.
    location_consistency_score = 10.0 # Placeholder
    device_consistency_score = 10.0 # Placeholder
    
    return min(100.0, max(0.0, account_age_score + kyc_score + location_consistency_score + device_consistency_score))


async def _calculate_risk_signals_score(db: AsyncSession, agent_id: int, transactions: list) -> float:
    """Calculate Risk Signals Score (lower is better, then inverse to 0-100)."""
    risk_score = 100.0 # Start with perfect, deduct for risk signals

    # Dormancy periods (conceptual) - would compare activity to historical
    # Suspicious transaction spikes (conceptual) - would analyze std dev of volume/amount
    
    # Check for recent risk events logged by the system
    recent_risk_events = (await db.execute(select(func.count()).filter(
        and_(
            models.RiskEvent.agent_id == agent_id,
            models.RiskEvent.timestamp >= datetime.now() - timedelta(days=7),
            models.RiskEvent.severity.in_(["high", "critical"])
        )
    ))).scalar_one()

    if recent_risk_events > 0:
        risk_score -= (recent_risk_events * 20) # Deduct 20 for each recent high/critical event
    
    # Example: If agent has high float balance, reduce perceived risk
    result = await db.execute(select(models.Agent).filter(models.Agent.id == agent_id))
    agent = result.scalars().first()
    if agent and agent.float_balance < 50: # Very low float, higher risk
        risk_score -= 10

    return min(100.0, max(0.0, risk_score))


async def calculate_credit_score(db: AsyncSession, agent_id: int) -> int:
    """
    Calculates the agent's overall credit score based on the Enterprise Risk Model formula.
    """
    result = await db.execute(select(models.Agent).filter(models.Agent.id == agent_id))
    agent = result.scalars().first()
    if not agent:
        return 0 # Cannot score non-existent agent

    recent_transactions = await _get_agent_transactions_data(db, agent.id)

    volume_score_val = _calculate_volume_score(recent_transactions)
    consistency_score_val = _calculate_consistency_score(recent_transactions)
    repayment_score_val = await _calculate_repayment_score(db, agent.id)
    trust_score_val = await _calculate_trust_score(db, agent, recent_transactions)
    risk_signals_score_val = await _calculate_risk_signals_score(db, agent.id, recent_transactions)
    
    # Invert Risk Signals Score for formula (as it's a deduction)
    risk_component_score = 100 - risk_signals_score_val # Higher risk signals = lower component score

    # Apply formula weights
    credit_score = int(
        (volume_score_val * 0.25) +
        (consistency_score_val * 0.20) +
        (repayment_score_val * 0.25) +
        (trust_score_val * 0.15) +
        (risk_component_score * 0.15) # Use the inverted score here
    )
    
    # Ensure score is within 0-100
    credit_score = min(100, max(0, credit_score))
    
    # Store or update AgentRiskProfile
    result = await db.execute(select(models.AgentRiskProfile).filter(models.AgentRiskProfile.agent_id == agent_id))
    risk_profile = result.scalars().first()
    if not risk_profile:
        risk_profile = models.AgentRiskProfile(agent_id=agent_id)
        db.add(risk_profile)
    
    risk_profile.credit_score = credit_score
    risk_profile.risk_level = _interpret_score_to_risk_level(credit_score)
    risk_profile.recommended_limit = await auto_loan_limit_calculator(db, agent.id, credit_score, recent_transactions)
    risk_profile.last_calculated = datetime.now()
    
    await db.commit()
    await db.refresh(risk_profile)

    return credit_score

def _interpret_score_to_risk_level(score: int) -> str:
    if score >= 85:
        return "Very Safe"
    elif score >= 70:
        return "Safe"
    elif score >= 55:
        return "Medium"
    elif score >= 40:
        return "Risky"
    else:
        return "Dangerous"

async def auto_loan_limit_calculator(db: AsyncSession, agent_id: int, credit_score: int, transactions: list) -> float:
    """
    Calculates the eligible loan limit for an agent based on their credit score and average daily volume.
    """
    # Calculate Average Daily Volume (ADV)
    total_volume = sum(tx.amount for tx in transactions)
    # Assume scoring period is 30 days, as per _get_agent_transactions_data
    avg_daily_volume = total_volume / 30 if total_volume > 0 else 0

    trust_multiplier = 0.0
    if credit_score >= 85:
        trust_multiplier = 1.5
    elif credit_score >= 70:
        trust_multiplier = 1.0
    else: # For scores below 70, use a lower multiplier
        trust_multiplier = 0.5
    
    eligible_loan = (avg_daily_volume * 7) * trust_multiplier
    
    # Ensure it does not exceed the global maximum loan amount per agent
    return min(eligible_loan, settings.MAX_LOAN_AMOUNT_PER_AGENT)


async def create_loan_application(db: AsyncSession, agent_id: int, application: LoanApplicationCreate):
    result = await db.execute(select(models.Agent).filter(models.Agent.id == agent_id))
    agent = result.scalars().first()
    risk_score = await calculate_risk_score(db, agent_id, application)
    db_application = models.LoanApplication(
        **application.model_dump(),
        user_id=agent.user_id if agent else None,
        agent_id=agent_id,
        risk_score=risk_score,
        status="pending_admin_approval",
    )
    db.add(db_application)
    await db.commit()
    await db.refresh(db_application)
    return db_application

async def approve_loan_application(
    db: AsyncSession,
    application_id: int,
    admin_user_id: int,
    approved_amount: float | None = None,
    fee_percentage: float | None = None,
    offered_repayment_duration: int | None = None,
    review_note: str | None = None,
):
    result = await db.execute(select(models.LoanApplication).filter(models.LoanApplication.id == application_id))
    db_application = result.scalars().first()
    if not db_application:
        return None

    result = await db.execute(select(models.Agent).filter(models.Agent.id == db_application.agent_id))
    agent = result.scalars().first()
    if not agent:
        # Should not happen if application has a valid agent_id
        db_application.status = "rejected"
        db_application.rejected_date = datetime.now()
        await db.commit()
        await db.refresh(db_application)
        return db_application

    result = await db.execute(select(models.User).filter(models.User.id == agent.user_id))
    user = result.scalars().first()
    if not user or not user.is_verified:
        db_application.status = "rejected"
        db_application.rejected_date = datetime.now()
        await db.commit()
        await db.refresh(db_application)
        return db_application

    # Risk engine output is advisory; admin decision is final.
    credit_score = await calculate_credit_score(db, db_application.agent_id)
    db_application.risk_score = credit_score

    recent_transactions = await _get_agent_transactions_data(db, db_application.agent_id)
    recommended_limit = await auto_loan_limit_calculator(db, db_application.agent_id, credit_score, recent_transactions)
    risk_level = _interpret_score_to_risk_level(credit_score)

    default_fee = 3.0 if risk_level == "Very Safe" else 5.0 if risk_level == "Safe" else 8.0
    final_amount = approved_amount if approved_amount is not None else min(db_application.amount, recommended_limit)
    final_fee = fee_percentage if fee_percentage is not None else default_fee
    final_duration = offered_repayment_duration if offered_repayment_duration is not None else db_application.repayment_duration

    if final_amount <= 0:
        db_application.status = "rejected"
        db_application.rejected_date = datetime.now()
        db_application.reviewed_at = datetime.now()
        db_application.reviewed_by_admin_id = admin_user_id
        db_application.review_note = review_note or "Rejected: approved amount must be positive."
        await db.commit()
        await db.refresh(db_application)
        return db_application

    db_application.status = "approved"
    db_application.approved_amount = min(final_amount, recommended_limit)
    db_application.fee_percentage = final_fee
    db_application.offered_repayment_duration = final_duration
    db_application.approved_date = datetime.now()
    db_application.reviewed_at = datetime.now()
    db_application.reviewed_by_admin_id = admin_user_id
    db_application.review_note = review_note
    await db.commit()
    await db.refresh(db_application)
    return db_application


async def reject_loan_application(
    db: AsyncSession,
    application_id: int,
    admin_user_id: int,
    review_note: str | None = None,
):
    result = await db.execute(select(models.LoanApplication).filter(models.LoanApplication.id == application_id))
    db_application = result.scalars().first()
    if not db_application:
        return None

    db_application.status = "rejected"
    db_application.rejected_date = datetime.now()
    db_application.reviewed_at = datetime.now()
    db_application.reviewed_by_admin_id = admin_user_id
    db_application.review_note = review_note
    await db.commit()
    await db.refresh(db_application)
    return db_application

async def disburse_loan(db: AsyncSession, application_id: int):
    result = await db.execute(select(models.LoanApplication).filter(models.LoanApplication.id == application_id))
    db_application = result.scalars().first()
    if not db_application or db_application.status != "approved" or not db_application.approved_amount:
        return None

    # Create the actual loan record
    offered_duration = int(db_application.offered_repayment_duration or db_application.repayment_duration or 0)
    repayment_due_date = datetime.now() + timedelta(days=offered_duration)
    loan_principal = _money(db_application.approved_amount)
    loan_fee_percentage = _money(db_application.fee_percentage)
    loan_fee_amount = _money(loan_principal * (loan_fee_percentage / 100.0))
    total_outstanding = _money(loan_principal + loan_fee_amount)
    
    db_loan = models.Loan(
        user_id=db_application.user_id,
        agent_id=db_application.agent_id,
        application_id=db_application.id,
        amount=loan_principal, # Original approved principal
        repayment_duration=offered_duration,
        base_fee_percentage=loan_fee_percentage,
        base_fee_amount=loan_fee_amount,
        late_fee_percentage=LATE_LOAN_FEE_PERCENTAGE,
        late_fee_amount=0.0,
        outstanding_balance=total_outstanding, # Principal + Fee
        repayment_due_date=repayment_due_date,
        status="active"
    )
    
    db.add(db_loan)

    result = await db.execute(select(models.Agent).filter(models.Agent.id == db_application.agent_id))
    agent = result.scalars().first()
    if not agent:
        return None

    result = await db.execute(select(models.User).filter(models.User.id == agent.user_id))
    user = result.scalars().first()
    if not user:
        return None
    if db_loan.user_id is None:
        db_loan.user_id = user.id
    if db_application.user_id is None:
        db_application.user_id = user.id

    ledger_service = LedgerService(db)
    transaction_engine = TransactionEngine(db, ledger_service)
    await transaction_engine.process_transaction(
        user_id=user.id,
        transaction_type=TransactionType.LOAN_DISBURSE,
        amount=loan_principal,
        agent_id=agent.id,
        metadata={
            "loan_id": db_loan.id,
            "application_id": db_application.id,
            "fee_percentage": loan_fee_percentage,
            "base_fee_amount": loan_fee_amount,
            "wallet_loan_balance_increase": total_outstanding,
            "repayment_due_date": repayment_due_date.isoformat(),
            "repayment_duration": offered_duration,
        },
    )

    db_application.status = "disbursed"
    result = await db.execute(select(models.Wallet).filter(models.Wallet.user_id == user.id))
    wallet = result.scalars().first()
    if wallet:
        await sync_wallet_loan_balance(
            db,
            user.id,
            wallet=wallet,
            active_agent_id=agent.id,
        )
    await db.commit()
    await db.refresh(db_application)
    await db.refresh(db_loan)
    return db_loan

async def repay_loan(db: AsyncSession, loan_id: int, repayment_amount: float):
    result = await db.execute(select(models.Loan).filter(models.Loan.id == loan_id))
    db_loan = result.scalars().first()
    if not db_loan:
        return None

    owner_user_id = db_loan.user_id
    if owner_user_id is None and db_loan.agent_id:
        result = await db.execute(select(models.Agent).filter(models.Agent.id == db_loan.agent_id))
        agent = result.scalars().first()
        owner_user_id = agent.user_id if agent else None
    if owner_user_id is None:
        return None

    return await repay_loan_for_user(
        db,
        owner_user_id,
        loan_id,
        repayment_amount,
        trigger="manual",
    )


async def calculate_risk_score(db: AsyncSession, agent_id: int, application: LoanApplicationCreate | None = None) -> int:
    return await calculate_credit_score(db, agent_id)


async def get_max_eligible_loan(db: AsyncSession, risk_score: int) -> float:
    if risk_score >= 85:
        return settings.MAX_LOAN_AMOUNT_PER_AGENT
    if risk_score >= 70:
        return settings.MAX_LOAN_AMOUNT_PER_AGENT * 0.75
    if risk_score >= 55:
        return settings.MAX_LOAN_AMOUNT_PER_AGENT * 0.5
    return settings.MAX_LOAN_AMOUNT_PER_AGENT * 0.25

async def get_agent_loan_applications(db: AsyncSession, agent_id: int):
    result = await db.execute(select(models.LoanApplication).filter(models.LoanApplication.agent_id == agent_id))
    return result.scalars().all()

async def get_agent_loans(db: AsyncSession, agent_id: int):
    result = await db.execute(select(models.Loan).filter(models.Loan.agent_id == agent_id))
    return result.scalars().all()

async def get_loan_overview(db: AsyncSession) -> LoanOverviewResponse:
    total_active_loans = (
        await db.execute(
            select(func.count(models.Loan.id)).filter(models.Loan.status.in_(OPEN_LOAN_STATUSES))
        )
    ).scalar_one()
    total_exposure = (
        await db.execute(
            select(func.sum(models.Loan.outstanding_balance)).filter(models.Loan.status.in_(OPEN_LOAN_STATUSES))
        )
    ).scalar_one()
    
    if total_exposure is None:
        total_exposure = 0.0

    # Placeholder for default risk % and repayment rate - these would require more complex logic and data
    default_risk_percentage = 0.0 # To be calculated based on historical defaults
    repayment_rate = 0.0 # To be calculated based on historical repayment vs. disbursed

    return schemas.LoanOverviewResponse(
        total_active_loans=total_active_loans,
        total_exposure=total_exposure,
        default_risk_percentage=default_risk_percentage,
        repayment_rate=repayment_rate
    )

async def get_agent_credit_profile(db: AsyncSession, agent_id: int) -> AgentCreditProfileResponse:
    result = await db.execute(select(models.Agent).filter(models.Agent.id == agent_id))
    agent = result.scalars().first()
    if not agent:
        return None

    result = await db.execute(select(models.User).filter(models.User.id == agent.user_id))
    user = result.scalars().first()
    
    # Calculate credit score (re-use existing logic or refine)
    # For now, let's assume a dummy risk score (e.g., from a recent application if available)
    result = await db.execute(select(models.LoanApplication).filter(
        models.LoanApplication.agent_id == agent.id
    ).order_by(models.LoanApplication.application_date.desc()))
    latest_application = result.scalars().first()
    
    credit_score = latest_application.risk_score if latest_application else None
    if credit_score is None:
        # If no applications, provide a default or calculate a basic one
        credit_score = await calculate_credit_score(db, agent.id) # Use the new comprehensive score

    # max_eligible_loan calculation now uses the auto_loan_limit_calculator directly
    recent_transactions = await _get_agent_transactions_data(db, agent.id)
    max_eligible_loan = await auto_loan_limit_calculator(db, agent.id, credit_score, recent_transactions)

    result = await db.execute(select(models.Loan).filter(
        models.Loan.agent_id == agent.id,
        models.Loan.status.in_(OPEN_LOAN_STATUSES)
    ))
    current_loan = result.scalars().first()

    current_loan_id = current_loan.id if current_loan else None
    current_loan_amount = current_loan.amount if current_loan else None
    current_loan_outstanding_balance = current_loan.outstanding_balance if current_loan else None

    repayment_progress_percentage = None
    total_loan_with_fees = 0.0
    if current_loan and current_loan.amount > 0:
        total_loan_with_fees = _loan_total_due_amount(current_loan)

        if total_loan_with_fees > 0:
            repayment_progress_percentage = ((total_loan_with_fees - current_loan.outstanding_balance) / total_loan_with_fees) * 100
            repayment_progress_percentage = max(0, min(100, repayment_progress_percentage)) # Ensure it's between 0 and 100
    
    # Placeholder for risk flags
    risk_flags = []
    # Ensure current_loan is not None before accessing its attributes
    if current_loan and current_loan.repayment_due_date < datetime.now() and current_loan.status in OPEN_LOAN_STATUSES:
        risk_flags.append("loan_overdue")
    if agent.is_borrowing_frozen:
        risk_flags.append("borrowing_frozen")
    # Ensure user is not None before accessing its attributes
    if user and user.email and user.email.endswith("example.com"): # Example: email domain based flag (check if user exists)
        risk_flags.append("suspicious_email_domain")
    
    # Also check risk events
    result = await db.execute(select(models.AgentRiskProfile).filter(models.AgentRiskProfile.agent_id == agent.id))
    agent_risk_profile = result.scalars().first()
    if agent_risk_profile:
        risk_flags.append(f"Risk Level: {agent_risk_profile.risk_level}")


    return AgentCreditProfileResponse(
        agent_id=agent.id,
        user_id=agent.user_id,
        full_name=user.full_name if user else "N/A",
        email=user.email if user else "N/A",
        credit_score=credit_score,
        max_eligible_loan_amount=max_eligible_loan,
        current_loan_id=current_loan_id,
        current_loan_amount=current_loan_amount,
        current_loan_outstanding_balance=current_loan_outstanding_balance,
        repayment_progress_percentage=repayment_progress_percentage,
        risk_flags=risk_flags
    )
