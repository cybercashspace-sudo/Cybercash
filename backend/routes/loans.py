from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime

from .. import models # Keep models import as it's used directly
from backend.database import get_db
from backend.dependencies.auth import get_current_user
from ..services import loan_service # Import your loan_service
from backend.schemas.loan_application import LoanApplicationCreate, LoanApplicationInDB # Explicit imports
from backend.schemas.loan_admin import AgentCreditProfileResponse, LoanApplicationDecisionRequest # Explicit import
from backend.schemas.loan import LoanInDB, LoanAutoDeductionUpdateRequest, LoanAutoDeductionResponse, LoanPolicyResponse # Explicit import
from backend.core.config import settings # Needed for RISK_SCORE_APPROVAL_THRESHOLD

router = APIRouter(
    prefix="/loans",
    tags=["Loans"]
)

# Helper function to get the current active agent for agent-facing endpoints
async def get_current_active_agent_for_loans(
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> models.Agent:
    result = await db.execute(select(models.Agent).filter(models.Agent.user_id == current_user.id))
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

@router.get("/my-eligibility", response_model=AgentCreditProfileResponse)
async def get_my_loan_eligibility(
    db: AsyncSession = Depends(get_db),
    agent: models.Agent = Depends(get_current_active_agent_for_loans)
):
    """
    Agent view: Get their loan eligibility, credit score, max eligible loan, etc. (Screen 1)
    """
    try:
        profile = await loan_service.get_agent_credit_profile(db=db, agent_id=agent.id)
        if not profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent credit profile not found.")
        return profile
    finally:
        await db.close()

@router.post("/preview-offer", response_model=LoanApplicationInDB)
async def preview_loan_offer(
    application_request: LoanApplicationCreate,
    db: AsyncSession = Depends(get_db),
    agent: models.Agent = Depends(get_current_active_agent_for_loans)
):
    """
    Agent view: Simulate a loan application to get an instant offer (Screen 2).
    This does not persist the application but calculates the potential offer.
    """
    try:
        if agent.is_borrowing_frozen:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Agent borrowing is currently frozen by administration."
            )

        # For simulation, create a dummy application object to pass to risk/approval logic
        # This won't be committed to the DB
        simulated_application = models.LoanApplication(
            agent_id=agent.id,
            amount=application_request.amount,
            repayment_duration=application_request.repayment_duration,
            purpose=application_request.purpose,
            status="simulated",
            application_date=datetime.now()
        )
        
        # Calculate risk score (from loan_service, but directly)
        risk_score = await loan_service.calculate_risk_score(db, agent.id, application_request)
        simulated_application.risk_score = risk_score

        # Simulate loan offer generation (similar to approve_loan_application but without status changes)
        approved_amount = 0.0
        fee_percentage = 0.0
        offered_repayment_duration = application_request.repayment_duration

        if risk_score >= settings.RISK_SCORE_APPROVAL_THRESHOLD:
            # Need to ensure get_max_eligible_loan is also async in loan_service
            max_eligible = await loan_service.get_max_eligible_loan(db, risk_score)
            approved_amount = min(application_request.amount, max_eligible)
            
            if risk_score >= 80:
                fee_percentage = 3.0
            elif risk_score >= 65:
                fee_percentage = 5.0
            else:
                fee_percentage = 8.0
        
        simulated_application.approved_amount = approved_amount
        simulated_application.fee_percentage = fee_percentage
        simulated_application.offered_repayment_duration = offered_repayment_duration

        return LoanApplicationInDB.from_orm(simulated_application)
    finally:
        await db.close()


@router.post("/apply", response_model=LoanApplicationInDB)
async def apply_for_loan(
    application: LoanApplicationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        db_application = await loan_service.create_self_service_loan(
            db=db,
            user=current_user,
            application=application,
        )
        return db_application
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    finally:
        await db.close()


@router.get("/my-policy", response_model=LoanPolicyResponse)
async def get_my_loan_policy(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        policy = await loan_service.get_loan_policy_for_user(db=db, user=current_user)
        return LoanPolicyResponse(**policy)
    finally:
        await db.close()

@router.get("/my-applications/{application_id}", response_model=LoanApplicationInDB)
async def get_my_loan_application_status(
    application_id: int,
    db: AsyncSession = Depends(get_db),
    agent: models.Agent = Depends(get_current_active_agent_for_loans)
):
    """
    Agent view: Check the status and decision of a specific loan application (Screen 3).
    """
    try:
        result = await db.execute(select(models.LoanApplication).filter(
            models.LoanApplication.id == application_id,
            models.LoanApplication.agent_id == agent.id
        ))
        application = result.scalars().first()
        if not application:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan application not found.")
        return application
    finally:
        await db.close()

@router.get("/my-active-loan", response_model=Optional[LoanInDB])
async def get_my_active_loan(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Get details of the current user's open loan, including overdue balances.
    """
    try:
        maintenance = await loan_service.run_loan_maintenance_for_user(
            db=db,
            user_id=current_user.id,
            allow_auto_deduction=False,
        )
        return maintenance.get("loan")
    finally:
        await db.close()

@router.get("/agent/{agent_id}/applications", response_model=List[LoanApplicationInDB])
async def get_agent_applications(agent_id: int, db: AsyncSession = Depends(get_db)):
    try:
        applications = await loan_service.get_agent_loan_applications(db=db, agent_id=agent_id)
        if not applications:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No loan applications found for this agent")
        return applications
    finally:
        await db.close()

@router.get("/agent/{agent_id}/all", response_model=List[LoanInDB])
async def get_agent_loans(agent_id: int, db: AsyncSession = Depends(get_db)):
    try:
        loans = await loan_service.get_agent_loans(db=db, agent_id=agent_id)
        if not loans:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No loans found for this agent")
        return loans
    finally:
        await db.close()

@router.post("/{application_id}/approve", response_model=LoanApplicationInDB)
async def approve_application(
    application_id: int,
    request: LoanApplicationDecisionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can perform this action"
        )
    if request.decision == "rejected":
        db_application = await loan_service.reject_loan_application(
            db=db,
            application_id=application_id,
            admin_user_id=current_user.id,
            review_note=request.review_note,
        )
    else:
        db_application = await loan_service.approve_loan_application(
            db=db,
            application_id=application_id,
            admin_user_id=current_user.id,
            approved_amount=request.approved_amount,
            fee_percentage=request.fee_percentage,
            offered_repayment_duration=request.offered_repayment_duration,
            review_note=request.review_note,
        )

    try:
        if not db_application:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan application not found or cannot be approved")
        return db_application
    finally:
        await db.close()


@router.get("/auto-deduction", response_model=LoanAutoDeductionResponse)
async def get_loan_auto_deduction_setting(
    db: AsyncSession = Depends(get_db),
    agent: models.Agent = Depends(get_current_active_agent_for_loans)
):
    """
    Agent view: Get the current loan auto-deduction toggle state.
    """
    try:
        return LoanAutoDeductionResponse(
            agent_id=agent.id,
            enabled=bool(getattr(agent, "loan_auto_deduction_enabled", True)),
        )
    finally:
        await db.close()


@router.patch("/auto-deduction", response_model=LoanAutoDeductionResponse)
async def update_loan_auto_deduction_setting(
    request: LoanAutoDeductionUpdateRequest,
    db: AsyncSession = Depends(get_db),
    agent: models.Agent = Depends(get_current_active_agent_for_loans)
):
    """
    Agent view: Enable or disable automatic loan repayment deduction.
    """
    try:
        agent.loan_auto_deduction_enabled = request.enabled
        db.add(agent)
        await db.commit()
        await db.refresh(agent)
        return LoanAutoDeductionResponse(agent_id=agent.id, enabled=agent.loan_auto_deduction_enabled)
    finally:
        await db.close()

@router.post("/{application_id}/disburse", response_model=LoanInDB)
async def disburse_loan(
    application_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can perform this action"
        )
    try:
        db_loan = await loan_service.disburse_loan(db=db, application_id=application_id)
        if not db_loan:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not disburse loan (application not found or not approved)")
        return db_loan
    finally:
        await db.close()

@router.post("/{loan_id}/repay", response_model=LoanInDB)
async def repay_loan(
    loan_id: int,
    repayment_amount: float,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        db_loan = await loan_service.repay_loan_for_user(
            db=db,
            user_id=current_user.id,
            loan_id=loan_id,
            repayment_amount=repayment_amount,
            trigger="manual",
        )
        if not db_loan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found or already repaid")
        return db_loan
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    finally:
        await db.close()
