from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.transaction_types import TransactionType
from backend.database import get_db
from backend.models import Agent, Payment, Transaction, User, Wallet
from backend.services.compliance_service import ensure_daily_window
from backend.services.flutterwave_service import FlutterwaveService, get_flutterwave_service
from backend.services.ledger_service import LedgerService, get_ledger_service
from backend.services.settings_service import (
    get_or_create_platform_settings,
    get_or_create_user_settings,
    resolve_effective_withdrawal_limit,
)
from utils.network import (
    detect_flutterwave_network,
    is_valid_flutterwave_momo_number,
    normalize_flutterwave_momo_number,
    normalize_ghana_number,
)


class PayoutService:
    def __init__(
        self,
        db: AsyncSession,
        ledger_service: LedgerService,
        flutterwave_service: FlutterwaveService,
    ) -> None:
        self.db = db
        self.ledger_service = ledger_service
        self.flutterwave_service = flutterwave_service

    @staticmethod
    def _role_label(user: User) -> str:
        role = str(getattr(user, "role", "") or "").strip().lower()
        if role:
            return role
        if getattr(user, "is_admin", False):
            return "admin"
        if getattr(user, "is_agent", False):
            return "agent"
        return "user"

    @staticmethod
    def _parse_metadata(raw_metadata: Optional[str]) -> Dict[str, Any]:
        if not raw_metadata:
            return {}
        try:
            parsed = json.loads(raw_metadata)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    async def _get_or_create_wallet(self, user_id: int, currency: str = "GHS") -> Wallet:
        result = await self.db.execute(select(Wallet).filter(Wallet.user_id == user_id))
        wallet = result.scalars().first()
        if wallet:
            return wallet

        wallet = Wallet(user_id=user_id, currency=currency, balance=0.0)
        self.db.add(wallet)
        await self.db.flush()
        return wallet

    async def _get_active_agent(self, user_id: int) -> Agent:
        result = await self.db.execute(select(Agent).filter(Agent.user_id == user_id))
        agent = result.scalars().first()
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not registered as an agent.",
            )
        if str(agent.status or "").strip().lower() != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Agent account is not active.",
            )
        return agent

    def _build_reference(self, user: User) -> str:
        return f"CYBERCASH-PAYOUT-{user.id}-{uuid.uuid4().hex.upper()}"

    def _resolve_source_account(
        self,
        *,
        user: User,
        wallet: Wallet,
        agent: Optional[Agent],
        amount: float,
    ) -> Tuple[str, str, Any, float]:
        if wallet.is_frozen:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Wallet is frozen.",
            )

        role = self._role_label(user)

        if role == "agent":
            if not agent:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Agent account is required for agent payouts.",
                )
            source_balance = float(agent.commission_balance or 0.0)
            if source_balance < amount:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Insufficient commission balance for withdrawal.",
                )
            return "agent_commission", "Commissions Payable (Liability)", agent, source_balance

        source_balance = float(wallet.balance or 0.0)
        if source_balance < amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient wallet balance for withdrawal.",
            )
        return "wallet", "Customer Wallets (Liability)", wallet, source_balance

    async def initiate_momo_payout(
        self,
        *,
        current_user: User,
        amount: float,
        account_number: str,
        currency: str = "GHS",
        network: Optional[str] = None,
        notes: Optional[str] = None,
        requested_user_id: Optional[int] = None,
        beneficiary_name: Optional[str] = None,
    ) -> Payment:
        if requested_user_id is not None and int(requested_user_id) != int(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Withdrawals can only be requested for the authenticated user.",
            )

        role = self._role_label(current_user)
        if role not in {"admin", "agent"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Withdrawal not allowed.",
            )

        if not bool(getattr(current_user, "is_verified", False)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Complete account verification before requesting a withdrawal.",
            )

        if str(currency or "GHS").strip().upper() != "GHS":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only GHS mobile money withdrawals are supported.",
            )

        if float(amount or 0.0) <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Withdrawal amount must be positive.",
            )

        ensure_daily_window(current_user)
        daily_limit = float(getattr(current_user, "daily_limit", 0.0) or 0.0)
        daily_spent = float(getattr(current_user, "daily_spent", 0.0) or 0.0)
        if daily_limit and daily_spent + float(amount) > daily_limit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Daily withdrawal limit exceeded. Limit: {daily_limit:.2f}.",
            )

        user_settings = await get_or_create_user_settings(self.db, current_user.id)
        platform_settings = await get_or_create_platform_settings(self.db)
        effective_withdrawal_limit = resolve_effective_withdrawal_limit(
            current_user,
            user_settings=user_settings,
            platform_settings=platform_settings,
        )
        if effective_withdrawal_limit and float(amount) > effective_withdrawal_limit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Withdrawal limit exceeded. Limit: {effective_withdrawal_limit:.2f}.",
            )

        momo_number = normalize_ghana_number(account_number)
        if not is_valid_flutterwave_momo_number(momo_number):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only Ghana mobile money numbers are supported for withdrawals.",
            )

        detected_network = detect_flutterwave_network(momo_number)
        requested_network = str(network or "").strip().upper() or None
        if requested_network in {"TELECEL", "VODAFONE"}:
            requested_network = "VODAFONE"
        if requested_network and requested_network != detected_network:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Network mismatch. The supplied number resolves to {detected_network}, "
                    f"not {requested_network}."
                ),
            )

        wallet = await self._get_or_create_wallet(current_user.id, currency="GHS")
        agent: Optional[Agent] = None
        if role == "agent":
            agent = await self._get_active_agent(current_user.id)

        source_kind, source_ledger_account, source_object, source_balance_before = self._resolve_source_account(
            user=current_user,
            wallet=wallet,
            agent=agent,
            amount=float(amount),
        )

        flutterwave_number = normalize_flutterwave_momo_number(momo_number)
        internal_reference = self._build_reference(current_user)
        beneficiary = str(beneficiary_name or current_user.full_name or "CyberCash").strip()
        narration = str(notes or f"CyberCash withdrawal for {beneficiary}").strip()

        payment = Payment(
            user_id=current_user.id,
            amount=round(float(amount), 2),
            currency="GHS",
            type="withdrawal",
            processor="flutterwave",
            status="awaiting_confirmation",
            our_transaction_id=internal_reference,
            metadata_json=json.dumps(
                {
                    "method": "momo",
                    "requested_user_id": current_user.id,
                    "role": role,
                    "source_kind": source_kind,
                    "source_ledger_account": source_ledger_account,
                    "source_balance_before": round(source_balance_before, 2),
                    "momo_number_local": momo_number,
                    "momo_number_flutterwave": flutterwave_number,
                    "detected_network": detected_network,
                    "requested_network": requested_network,
                    "narration": narration,
                    "notes": notes,
                }
            ),
        )
        self.db.add(payment)
        await self.db.flush()

        transaction = Transaction(
            user_id=current_user.id,
            wallet_id=wallet.id,
            amount=round(float(amount), 2),
            currency="GHS",
            type=TransactionType.MOBILE_MONEY,
            status="awaiting_confirmation",
            provider="flutterwave",
            provider_reference=internal_reference,
            metadata_json=json.dumps(
                {
                    "payment_id": payment.id,
                    "reference": internal_reference,
                    "method": "momo",
                    "role": role,
                    "source_kind": source_kind,
                    "source_ledger_account": source_ledger_account,
                    "momo_number_local": momo_number,
                    "momo_number_flutterwave": flutterwave_number,
                    "detected_network": detected_network,
                    "requested_network": requested_network,
                    "narration": narration,
                    "notes": notes,
                }
            ),
        )
        self.db.add(transaction)
        await self.db.flush()

        if source_kind == "agent_commission":
            assert isinstance(source_object, Agent)
            source_object.commission_balance = float(source_object.commission_balance or 0.0) - float(amount)
            self.db.add(source_object)
        else:
            assert isinstance(source_object, Wallet)
            source_object.balance = float(source_object.balance or 0.0) - float(amount)
            self.db.add(source_object)

        current_user.daily_spent = float(current_user.daily_spent or 0.0) + float(amount)
        current_user.daily_spent_reset_at = current_user.daily_spent_reset_at or datetime.now(timezone.utc)
        self.db.add(current_user)

        await self.ledger_service.create_journal_entry(
            description=f"Mobile money payout initiation for user {current_user.id}",
            ledger_entries_data=[
                {"account_name": source_ledger_account, "debit": round(float(amount), 2), "credit": 0.0},
                {"account_name": "Cash (External Bank)", "debit": 0.0, "credit": round(float(amount), 2)},
            ],
            payment=payment,
            transaction=transaction,
            auto_commit=False,
        )

        await self.db.commit()
        await self.db.refresh(payment)
        await self.db.refresh(transaction)

        try:
            flutterwave_response = await self.flutterwave_service.initiate_transfer(
                account_number=momo_number,
                amount=float(amount),
                currency="GHS",
                reference=internal_reference,
                narration=narration,
                beneficiary_name=beneficiary,
                network=requested_network or detected_network,
                meta={
                    "payment_id": payment.id,
                    "transaction_id": transaction.id,
                    "user_id": current_user.id,
                    "role": role,
                    "source_kind": source_kind,
                    "source_ledger_account": source_ledger_account,
                },
            )
        except HTTPException as exc:
            await self._mark_failed_and_revert(
                payment_id=payment.id,
                transaction_id=transaction.id,
                user_id=current_user.id,
                amount=float(amount),
                source_kind=source_kind,
                source_ledger_account=source_ledger_account,
                reason=str(exc.detail or "Flutterwave transfer failed."),
            )
            raise
        except Exception as exc:
            await self._mark_failed_and_revert(
                payment_id=payment.id,
                transaction_id=transaction.id,
                user_id=current_user.id,
                amount=float(amount),
                source_kind=source_kind,
                source_ledger_account=source_ledger_account,
                reason=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to initiate Flutterwave transfer.",
            ) from exc

        transfer_data = flutterwave_response.get("data") or {}
        transfer_status = str(
            transfer_data.get("status")
            or flutterwave_response.get("transfer_status")
            or ""
        ).strip().upper()
        processor_reference = str(
            transfer_data.get("id")
            or transfer_data.get("transfer_code")
            or transfer_data.get("reference")
            or internal_reference
        ).strip()

        payment.processor_transaction_id = processor_reference
        payment.metadata_json = json.dumps(
            {
                **self._parse_metadata(payment.metadata_json),
                "flutterwave_response": flutterwave_response,
                "processor_reference": processor_reference,
                "processor_status": transfer_status,
            }
        )
        transaction.provider_reference = internal_reference
        transaction.metadata_json = json.dumps(
            {
                **self._parse_metadata(transaction.metadata_json),
                "flutterwave_response": flutterwave_response,
                "processor_reference": processor_reference,
                "processor_status": transfer_status,
            }
        )

        if transfer_status in {"SUCCESSFUL", "SUCCESS", "COMPLETED"}:
            payment.status = "successful"
            transaction.status = "completed"
        else:
            payment.status = "awaiting_confirmation"
            transaction.status = "awaiting_confirmation"

        self.db.add(payment)
        self.db.add(transaction)
        await self.db.commit()
        await self.db.refresh(payment)
        await self.db.refresh(transaction)
        return payment

    async def _mark_failed_and_revert(
        self,
        *,
        payment_id: int,
        transaction_id: int,
        user_id: int,
        amount: float,
        source_kind: str,
        source_ledger_account: str,
        reason: str,
    ) -> None:
        result = await self.db.execute(select(Payment).filter(Payment.id == payment_id))
        payment = result.scalars().first()
        result = await self.db.execute(select(Transaction).filter(Transaction.id == transaction_id))
        transaction = result.scalars().first()
        result = await self.db.execute(select(User).filter(User.id == user_id))
        user = result.scalars().first()
        result = await self.db.execute(select(Wallet).filter(Wallet.user_id == user_id))
        wallet = result.scalars().first()
        result = await self.db.execute(select(Agent).filter(Agent.user_id == user_id))
        agent = result.scalars().first()

        if not payment or not transaction or not user:
            return

        payment.status = "failed"
        transaction.status = "failed"

        if source_kind == "agent_commission" and agent:
            agent.commission_balance = float(agent.commission_balance or 0.0) + float(amount)
            self.db.add(agent)
        elif wallet:
            wallet.balance = float(wallet.balance or 0.0) + float(amount)
            self.db.add(wallet)

        user.daily_spent = max(0.0, float(user.daily_spent or 0.0) - float(amount))
        self.db.add(user)

        payment.metadata_json = json.dumps(
            {
                **self._parse_metadata(payment.metadata_json),
                "failure_reason": reason,
            }
        )
        transaction.metadata_json = json.dumps(
            {
                **self._parse_metadata(transaction.metadata_json),
                "failure_reason": reason,
            }
        )

        await self.ledger_service.create_journal_entry(
            description=f"Mobile money payout reversal for user {user_id}: {reason}",
            ledger_entries_data=[
                {"account_name": "Cash (External Bank)", "debit": round(float(amount), 2), "credit": 0.0},
                {"account_name": source_ledger_account, "debit": 0.0, "credit": round(float(amount), 2)},
            ],
            payment=payment,
            transaction=transaction,
            auto_commit=False,
        )

        payment.metadata_json = json.dumps(
            {
                **self._parse_metadata(payment.metadata_json),
                "failure_reason": reason,
            }
        )
        transaction.metadata_json = json.dumps(
            {
                **self._parse_metadata(transaction.metadata_json),
                "failure_reason": reason,
            }
        )

        self.db.add(payment)
        self.db.add(transaction)
        await self.db.commit()

    async def process_flutterwave_webhook(self, request: Request) -> Dict[str, Any]:
        if not self.flutterwave_service.webhook_hash:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Flutterwave webhook hash is not configured.",
            )

        signature = str(request.headers.get("verif-hash") or "").strip()
        if not signature or signature != self.flutterwave_service.webhook_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid webhook signature.",
            )

        payload = await request.json()
        event = str(payload.get("event") or "").strip().lower()
        data = payload.get("data") or {}

        reference = str(
            data.get("reference")
            or data.get("transfer_code")
            or data.get("id")
            or ""
        ).strip()
        if not reference:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Webhook payload missing transfer reference.",
            )

        transfer_id = str(
            data.get("id")
            or data.get("transfer_code")
            or ""
        ).strip()
        transfer_status = str(data.get("status") or event).strip().lower()

        result = await self.db.execute(
            select(Payment).filter(
                Payment.processor == "flutterwave",
                or_(
                    Payment.our_transaction_id == reference,
                    Payment.processor_transaction_id == transfer_id,
                ),
            )
        )
        payment = result.scalars().first()
        if not payment:
            return {"message": "Webhook processed: no matching payout found."}

        result = await self.db.execute(
            select(Transaction).filter(
                Transaction.provider == "flutterwave",
                Transaction.provider_reference == payment.our_transaction_id,
            )
        )
        transaction = result.scalars().first()

        if payment.status == "successful" and transaction and transaction.status == "completed":
            return {"message": "Webhook processed: payout already completed."}

        if transfer_id:
            payment.processor_transaction_id = transfer_id

        if any(token in transfer_status for token in ("success", "completed", "successful")):
            payment.status = "successful"
            if transaction:
                transaction.status = "completed"
                self.db.add(transaction)
            self.db.add(payment)
            await self.db.commit()
            return {"message": "Webhook processed: payout completed."}

        if any(token in transfer_status for token in ("fail", "error", "reverse", "declin")):
            metadata = self._parse_metadata(payment.metadata_json)
            source_kind = str(metadata.get("source_kind") or "wallet").strip()
            source_ledger_account = str(
                metadata.get("source_ledger_account")
                or "Customer Wallets (Liability)"
            ).strip()
            amount = float(payment.amount or 0.0)
            user_id = int(payment.user_id)

            result = await self.db.execute(select(User).filter(User.id == user_id))
            user = result.scalars().first()
            result = await self.db.execute(select(Wallet).filter(Wallet.user_id == user_id))
            wallet = result.scalars().first()
            result = await self.db.execute(select(Agent).filter(Agent.user_id == user_id))
            agent = result.scalars().first()

            if user:
                if source_kind == "agent_commission" and agent:
                    agent.commission_balance = float(agent.commission_balance or 0.0) + amount
                    self.db.add(agent)
                elif wallet:
                    wallet.balance = float(wallet.balance or 0.0) + amount
                    self.db.add(wallet)
                user.daily_spent = max(0.0, float(user.daily_spent or 0.0) - amount)
                self.db.add(user)

            payment.status = "failed"
            if transaction:
                transaction.status = "failed"
                self.db.add(transaction)

            await self.ledger_service.create_journal_entry(
                description=f"Flutterwave webhook reversal for payout {payment.id}",
                ledger_entries_data=[
                    {"account_name": "Cash (External Bank)", "debit": round(amount, 2), "credit": 0.0},
                    {"account_name": source_ledger_account, "debit": 0.0, "credit": round(amount, 2)},
                ],
                payment=payment,
                transaction=transaction,
                auto_commit=False,
            )

            payment.metadata_json = json.dumps(
                {
                    **metadata,
                    "processor_status": transfer_status,
                    "failure_reason": data.get("reason") or data.get("status") or event,
                }
            )
            if transaction:
                tx_metadata = self._parse_metadata(transaction.metadata_json)
                transaction.metadata_json = json.dumps(
                    {
                        **tx_metadata,
                        "processor_status": transfer_status,
                        "failure_reason": data.get("reason") or data.get("status") or event,
                    }
                )

            self.db.add(payment)
            if transaction:
                self.db.add(transaction)
            await self.db.commit()
            return {"message": "Webhook processed: payout failed and was reversed."}

        payment.status = "awaiting_confirmation"
        if transaction:
            transaction.status = "awaiting_confirmation"
            self.db.add(transaction)
        self.db.add(payment)
        await self.db.commit()
        return {"message": "Webhook processed: payout still pending."}


async def get_payout_service(
    db: AsyncSession = Depends(get_db),
    ledger_service: LedgerService = Depends(get_ledger_service),
    flutterwave_service: FlutterwaveService = Depends(get_flutterwave_service),
) -> PayoutService:
    return PayoutService(db=db, ledger_service=ledger_service, flutterwave_service=flutterwave_service)
