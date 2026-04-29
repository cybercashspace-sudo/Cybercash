from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from backend.dependencies.auth import get_current_user
from backend.models import User
from backend.schemas.payment import PaymentResponse
from backend.schemas.payout import WithdrawalRequest
from backend.services.payout_service import PayoutService, get_payout_service


router = APIRouter(tags=["Payouts"])


@router.post("/withdraw", response_model=PaymentResponse)
async def withdraw(
    request: WithdrawalRequest,
    current_user: User = Depends(get_current_user),
    payout_service: PayoutService = Depends(get_payout_service),
):
    return await payout_service.initiate_momo_payout(
        current_user=current_user,
        amount=request.amount,
        account_number=request.account_number,
        currency=request.currency,
        network=request.network,
        notes=request.notes,
        requested_user_id=request.user_id,
    )


@router.post("/webhooks/flutterwave", status_code=status.HTTP_200_OK)
async def flutterwave_webhook(
    request: Request,
    payout_service: PayoutService = Depends(get_payout_service),
):
    return await payout_service.process_flutterwave_webhook(request)
