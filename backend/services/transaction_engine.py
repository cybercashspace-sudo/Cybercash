from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, Dict, Any, List
from fastapi import Depends
import json
from datetime import datetime
from backend.database import get_db
from backend.models import Transaction, Wallet, User, Agent, Account, CryptoWallet, VirtualCard, Loan, RiskEvent
from backend.core.transaction_types import TransactionType, normalize_transaction_type
from backend.services.ledger_service import LedgerService, get_ledger_service
from backend.services.commission_service import record_commission
from backend.services.agent_startup_loan import get_withdrawable_agent_float
from backend.core.config import settings
from utils.network import normalize_ghana_number
import logging

logger = logging.getLogger(__name__)
ESCROW_MIN_DEAL_AMOUNT_GHS = float(getattr(settings, "ESCROW_MIN_DEAL_AMOUNT_GHS", 20.0))
ESCROW_CREATE_FEE_GHS = float(getattr(settings, "ESCROW_CREATE_FEE_GHS", 5.0))
ESCROW_RELEASE_FEE_GHS = float(getattr(settings, "ESCROW_RELEASE_FEE_GHS", 5.0))
INVESTMENT_MIN_AMOUNT_GHS = float(getattr(settings, "INVESTMENT_MIN_AMOUNT_GHS", 10.0))
INVESTMENT_MIN_DAYS = int(getattr(settings, "INVESTMENT_MIN_DAYS", 7))
INVESTMENT_MAX_DAYS = int(getattr(settings, "INVESTMENT_MAX_DAYS", 365))
INVESTMENT_RISK_FREE_ANNUAL_RATE = float(getattr(settings, "INVESTMENT_RISK_FREE_ANNUAL_RATE", 12.0))
INVESTMENT_PROFIT_FEE_RATE = 0.10
INVESTMENT_ALLOWED_DURATIONS_DAYS = (7, 14, 30, 60, 90, 180, 365)


def _parse_metadata_json(raw_metadata: Optional[str]) -> Dict[str, Any]:
    if not raw_metadata:
        return {}
    try:
        parsed = json.loads(raw_metadata)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}

class TransactionEngine:
    def __init__(self, db: AsyncSession, ledger_service: LedgerService):
        self.db = db
        self.ledger_service = ledger_service

    async def _get_wallet(self, user_id: int) -> Wallet:
        result = await self.db.execute(select(Wallet).filter(Wallet.user_id == user_id))
        wallet = result.scalars().first()
        if not wallet:
            # Auto-create wallet if missing (for resilience)
            wallet = Wallet(user_id=user_id)
            self.db.add(wallet)
            await self.db.flush() # Ensure ID is generated
            # raise ValueError(f"Wallet not found for user {user_id}")
        return wallet

    async def _get_agent(self, agent_id: int) -> Agent:
        result = await self.db.execute(select(Agent).filter(Agent.id == agent_id))
        agent = result.scalars().first()
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        return agent

    async def _get_crypto_wallet(self, user_id: int, coin_type: str) -> CryptoWallet:
        result = await self.db.execute(select(CryptoWallet).filter(
            CryptoWallet.user_id == user_id, 
            CryptoWallet.coin_type == coin_type
        ))
        wallet = result.scalars().first()
        if not wallet:
             raise ValueError(f"Crypto Wallet ({coin_type}) not found for user {user_id}")
        return wallet

    async def _get_virtual_card(self, user_id: int, card_id: Optional[str] = None) -> VirtualCard:
        # If card_id is provided (provider_card_id or internal id), use it. 
        # For simplicity, if not provided, find the first active card.
        query = select(VirtualCard).filter(VirtualCard.user_id == user_id)
        if card_id:
            query = query.filter(VirtualCard.id == card_id) # Assuming internal ID for now
        
        result = await self.db.execute(query)
        card = result.scalars().first()
        if not card:
            raise ValueError("Virtual Card not found.")
        return card

    async def process_transaction(
        self,
        user_id: int,
        transaction_type: str,
        amount: float,
        agent_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Transaction:
        """
        The core engine that processes ALL transactions.
        Unified Flow: Request -> Validation -> Lock -> Ledger -> Balance Update -> Notification
        """
        # 1. Validation (Balance, Limits)
        wallet = await self._get_wallet(user_id)
        if wallet.is_frozen:
            raise ValueError("Wallet is frozen.")

        # Specific validations based on transaction type
        normalized_type = normalize_transaction_type(transaction_type)
        await self._run_pre_validation_checks(
            user_id=user_id,
            tx_type=normalized_type,
            amount=amount,
            metadata=metadata or {},
            agent_id=agent_id,
        )
        await self._validate_transaction(normalized_type, amount, wallet, agent_id, metadata)

        # 2. Transaction Lock (Handled by DB transaction block implicitly via async session)
        
        # 3. Create Transaction record (Initial Status: Pending)
        transaction = Transaction(
            user_id=user_id,
            wallet_id=wallet.id,
            agent_id=agent_id,
            type=normalized_type,
            amount=amount,
            status="pending",
            metadata_json=json.dumps(metadata or {}),
        )
        provider = str((metadata or {}).get("provider", "") or "").strip()
        provider_reference = str((metadata or {}).get("provider_reference", "") or "").strip()
        if provider:
            transaction.provider = provider
        if provider_reference:
            transaction.provider_reference = provider_reference
        self.db.add(transaction)
        await self.db.flush()

        try:
            # 4. Ledger Entries (Double Entry Accounting)
            ledger_entries = await self._generate_ledger_entries(transaction, wallet, agent_id, metadata)
            
            await self.ledger_service.create_journal_entry(
                description=f"{normalized_type} for user {user_id}",
                ledger_entries_data=ledger_entries,
                transaction=transaction
            )

            # 5. Update Denormalized Wallet Balances (The "State Change")
            await self._update_wallet_balances(transaction, wallet, agent_id, metadata)

            commission_amount = float((metadata or {}).get("commission", 0.0))
            if agent_id and commission_amount:
                await record_commission(
                    self.db,
                    agent_id=agent_id,
                    user_id=user_id,
                    amount=commission_amount,
                    currency=wallet.currency or "GHS",
                    commission_type=f"{normalized_type}_COMMISSION",
                    status="accrued",
                    transaction=transaction,
                    metadata={"source": "transaction_engine"},
                )

            # 6. Status Update
            transaction.status = "completed"
            await self.db.commit()
            await self.db.refresh(transaction)
            await self._run_post_commit_hooks(transaction, metadata)
            
            # 7. Real-Time Notification
            await self._send_notification(user_id, f"Transaction {normalized_type} of {amount} completed.")
            
            return transaction

        except Exception as e:
            await self.db.rollback()
            # Persist a failed transaction record for operational recovery tooling.
            try:
                failure_metadata = dict(metadata or {})
                failure_metadata["failed_reason"] = str(e)
                failure_metadata["failed_at"] = datetime.utcnow().isoformat()
                failed_tx = Transaction(
                    user_id=user_id,
                    wallet_id=wallet.id,
                    agent_id=agent_id,
                    type=normalized_type,
                    amount=amount,
                    currency=wallet.currency or "GHS",
                    status="failed",
                    metadata_json=json.dumps(failure_metadata),
                )
                self.db.add(failed_tx)
                await self.db.commit()
            except Exception as persist_exc:
                await self.db.rollback()
                logger.error(f"Failed to persist failed transaction record: {persist_exc}")

            logger.error(f"Transaction failed: {str(e)}")
            raise e

    async def confirm_transaction(self, transaction_id: int) -> Transaction:
        """
        Finalizes a pending transaction (e.g., from external webhook callback).
        Executes Ledger and Wallet updates.
        """
        result = await self.db.execute(
            select(Transaction).filter(Transaction.id == transaction_id).with_for_update()
        )
        transaction = result.scalars().first()
        
        if not transaction:
            raise ValueError("Transaction not found.")
        if transaction.status == "completed":
            return transaction
        if transaction.status != "pending":
            raise ValueError(f"Transaction cannot be confirmed. Current status: {transaction.status}")

        wallet = None
        try:
            wallet_result = await self.db.execute(
                select(Wallet).filter(Wallet.id == transaction.wallet_id).with_for_update()
            )
            wallet = wallet_result.scalars().first()
        except Exception:
            wallet = None

        if not wallet:
            wallet = await self._get_wallet(transaction.user_id)
            if transaction.wallet_id != wallet.id:
                transaction.wallet_id = wallet.id
                await self.db.flush()
        agent_id = transaction.agent_id
        
        # Re-construct metadata if possible, or assume minimal needs for confirmation
        # Note: In a real system, metadata should be stored in the Transaction model JSON field.
        # Since we don't have it explicitly stored/retrieved here, we proceed with caution.
        # Most "confirmable" transactions (deposits) don't need complex metadata for ledgering 
        # other than amount and type, unless commissions are involved.
        metadata = json.loads(transaction.metadata_json) if transaction.metadata_json else {}

        try:
            # 4. Ledger Entries
            ledger_entries = await self._generate_ledger_entries(transaction, wallet, agent_id, metadata)
            
            await self.ledger_service.create_journal_entry(
                description=f"{transaction.type} Confirmed for user {transaction.user_id}",
                ledger_entries_data=ledger_entries,
                transaction=transaction,
                auto_commit=False,
            )

            # 5. Update Balances
            await self._update_wallet_balances(transaction, wallet, agent_id, metadata)

            # 6. Status Update
            transaction.status = "completed"
            await self.db.commit()
            await self.db.refresh(transaction)
            await self._run_post_commit_hooks(transaction, metadata)
            
            # 7. Notification
            await self._send_notification(transaction.user_id, f"Transaction {transaction.type} of {transaction.amount} confirmed.")
            
            return transaction
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Transaction confirmation failed: {str(e)}")
            raise e

    async def _run_post_commit_hooks(self, transaction: Transaction, metadata: Optional[Dict[str, Any]] = None) -> None:
        metadata = metadata or {}
        tx_type = normalize_transaction_type(transaction.type)
        target_user_ids: set[int] = set()

        if tx_type in {
            TransactionType.FUNDING,
            TransactionType.AGENT_DEPOSIT,
            TransactionType.CARD_WITHDRAW,
            TransactionType.INVESTMENT_PAYOUT,
        }:
            target_user_ids.add(int(transaction.user_id))
        elif tx_type == TransactionType.ESCROW_RELEASE:
            recipient_id = metadata.get("recipient_id")
            try:
                if recipient_id is not None:
                    target_user_ids.add(int(recipient_id))
                else:
                    target_user_ids.add(int(transaction.user_id))
            except (TypeError, ValueError):
                target_user_ids.add(int(transaction.user_id))

        if not target_user_ids:
            return

        from backend.services import loan_service

        for target_user_id in target_user_ids:
            await loan_service.run_loan_maintenance_for_user(
                self.db,
                target_user_id,
                allow_auto_deduction=True,
            )

    async def _validate_transaction(
        self, 
        tx_type: str, 
        amount: float, 
        wallet: Wallet, 
        agent_id: Optional[int],
        metadata: Optional[Dict[str, Any]] = None
    ):
        metadata = metadata or {}
        if amount <= 0:
            raise ValueError("Amount must be positive.")

        fee = metadata.get("fee", 0.0)
        total_deduction = amount + fee

        # Fiat Withdrawals / Transfers
        if tx_type in [
            TransactionType.AGENT_WITHDRAWAL,
            TransactionType.TRANSFER,
            TransactionType.AIRTIME,
            TransactionType.DATA,
            TransactionType.CARD_LOAD,
            TransactionType.CARD_SPEND,
            TransactionType.INVESTMENT_CREATE,
            TransactionType.ESCROW_CREATE,
        ]:
            if wallet.balance < total_deduction:
                raise ValueError(f"Insufficient available balance. Required: {total_deduction}, Available: {wallet.balance}")
        
        # Agent Cash Deposit (Agent needs float)
        if tx_type == TransactionType.AGENT_DEPOSIT and agent_id:
            agent = await self._get_agent(agent_id)
            withdrawable_float = await get_withdrawable_agent_float(self.db, agent)
            if withdrawable_float < amount:
                raise ValueError(
                    "Insufficient withdrawable float. Startup loan funds are locked for airtime/data resale only."
                )

        # Crypto Withdrawal
        if tx_type == TransactionType.BTC_WITHDRAW:
            coin_type = metadata.get("coin_type")
            if not coin_type:
                raise ValueError("coin_type required for crypto withdrawal")
            crypto_wallet = await self._get_crypto_wallet(wallet.user_id, coin_type)
            if crypto_wallet.balance < total_deduction:
                raise ValueError(f"Insufficient crypto balance. Required: {total_deduction} {coin_type}")

        if tx_type == TransactionType.INVESTMENT_PAYOUT and wallet.investment_balance < amount:
            raise ValueError("Insufficient investment balance.")

        if tx_type == TransactionType.INVESTMENT_CREATE:
            if amount < INVESTMENT_MIN_AMOUNT_GHS:
                raise ValueError(f"Minimum investment amount is GHS {INVESTMENT_MIN_AMOUNT_GHS:.2f}.")
            duration_days = int(metadata.get("duration_days") or 0)
            if duration_days < INVESTMENT_MIN_DAYS or duration_days > INVESTMENT_MAX_DAYS:
                raise ValueError(
                    f"Investment duration must be between {INVESTMENT_MIN_DAYS} and {INVESTMENT_MAX_DAYS} days."
                )
            if duration_days not in INVESTMENT_ALLOWED_DURATIONS_DAYS:
                allowed = ", ".join(str(item) for item in INVESTMENT_ALLOWED_DURATIONS_DAYS)
                raise ValueError(f"Unsupported investment period. Choose one of: {allowed} days.")
            expected_rate = float(metadata.get("expected_rate", INVESTMENT_RISK_FREE_ANNUAL_RATE) or INVESTMENT_RISK_FREE_ANNUAL_RATE)
            if abs(expected_rate - INVESTMENT_RISK_FREE_ANNUAL_RATE) > 1e-9:
                raise ValueError(
                    f"Risk-free investment annual rate is fixed at {INVESTMENT_RISK_FREE_ANNUAL_RATE:.2f}%."
                )

        if tx_type == TransactionType.INVESTMENT_PAYOUT:
            investment_id = metadata.get("investment_id")
            if investment_id is None:
                raise ValueError("Investment ID is required for payout.")
            try:
                int(investment_id)
            except (TypeError, ValueError):
                raise ValueError("Investment ID is invalid.")

            net_profit = float(metadata.get("gain", 0.0) or 0.0)
            gross_profit = float(metadata.get("gross_profit", net_profit) or net_profit)
            profit_fee = float(metadata.get("fee", 0.0) or 0.0)
            fee_rate = float(metadata.get("profit_fee_rate", INVESTMENT_PROFIT_FEE_RATE) or INVESTMENT_PROFIT_FEE_RATE)

            if net_profit < 0 or gross_profit < 0 or profit_fee < 0:
                raise ValueError("Investment payout profit values cannot be negative.")
            if abs((gross_profit - profit_fee) - net_profit) > 0.05:
                raise ValueError("Investment payout profit breakdown is inconsistent.")
            if abs(fee_rate - INVESTMENT_PROFIT_FEE_RATE) > 1e-9:
                raise ValueError(f"Investment profit fee rate is fixed at {INVESTMENT_PROFIT_FEE_RATE * 100:.0f}%.")
            expected_profit_fee = round(gross_profit * INVESTMENT_PROFIT_FEE_RATE, 2)
            if abs(expected_profit_fee - profit_fee) > 0.05:
                raise ValueError(
                    f"Investment payout fee must be {INVESTMENT_PROFIT_FEE_RATE * 100:.0f}% of gross profit."
                )

        if tx_type == TransactionType.ESCROW_CREATE:
            recipient_id = metadata.get("recipient_id") if metadata else None
            if not recipient_id:
                raise ValueError("Recipient user ID is required for escrow deal creation.")
            try:
                recipient_id_int = int(recipient_id)
            except (TypeError, ValueError):
                raise ValueError("Recipient user ID is invalid.")
            if recipient_id_int == wallet.user_id:
                raise ValueError("Recipient must be a different user.")

            recipient_wallet_id = normalize_ghana_number(str(metadata.get("recipient_wallet_id", "")).strip())
            if not recipient_wallet_id:
                raise ValueError("Recipient registered number is required for escrow deal creation.")
            if len(recipient_wallet_id) != 10 or not recipient_wallet_id.isdigit():
                raise ValueError("Recipient registered number must be a valid 10-digit number.")

            escrow_fee = float(fee or 0.0)
            if abs(escrow_fee - ESCROW_CREATE_FEE_GHS) > 1e-9:
                raise ValueError(f"Escrow creation fee is fixed at GHS {ESCROW_CREATE_FEE_GHS:.2f}.")
            if amount < ESCROW_MIN_DEAL_AMOUNT_GHS:
                raise ValueError(f"Minimum escrow deal amount is GHS {ESCROW_MIN_DEAL_AMOUNT_GHS:.2f}.")
            if amount <= ESCROW_RELEASE_FEE_GHS:
                raise ValueError(
                    f"Escrow deal amount must exceed GHS {ESCROW_RELEASE_FEE_GHS:.2f} to keep receiver net payout positive."
                )

            recipient_result = await self.db.execute(select(User).filter(User.id == recipient_id_int))
            recipient = recipient_result.scalars().first()
            if not recipient or not recipient.is_active or not recipient.is_verified:
                raise ValueError("Recipient user not found, inactive, or unverified.")
            recipient_numbers = {
                normalize_ghana_number(str(recipient.momo_number or "").strip()),
                normalize_ghana_number(str(recipient.phone_number or "").strip()),
            }
            recipient_numbers = {number for number in recipient_numbers if number}
            if recipient_numbers and recipient_wallet_id not in recipient_numbers:
                raise ValueError("Recipient registered number does not match recipient account.")

        if tx_type == TransactionType.ESCROW_RELEASE:
            if wallet.escrow_balance < amount:
                raise ValueError("Insufficient escrow balance.")

            release_fee = float(fee or 0.0)
            if abs(release_fee - ESCROW_RELEASE_FEE_GHS) > 1e-9:
                raise ValueError(f"Escrow release fee is fixed at GHS {ESCROW_RELEASE_FEE_GHS:.2f}.")
            if amount <= release_fee:
                raise ValueError(
                    f"Escrow release amount must exceed the fixed GHS {ESCROW_RELEASE_FEE_GHS:.2f} receiver fee."
                )

            recipient_id = metadata.get("recipient_id")
            if recipient_id is None:
                raise ValueError("Recipient user ID is required for escrow release.")
            try:
                recipient_id_int = int(recipient_id)
            except (TypeError, ValueError):
                raise ValueError("Recipient user ID is invalid.")
            if recipient_id_int == wallet.user_id:
                raise ValueError("Escrow recipient must be a different user.")

            recipient_result = await self.db.execute(select(User).filter(User.id == recipient_id_int))
            recipient = recipient_result.scalars().first()
            if not recipient or not recipient.is_active or not recipient.is_verified:
                raise ValueError("Recipient user not found, inactive, or unverified.")

            recipient_wallet_id = normalize_ghana_number(str(metadata.get("recipient_wallet_id", "")).strip())
            if not recipient_wallet_id:
                raise ValueError("Recipient registered number is required for escrow release.")
            if len(recipient_wallet_id) != 10 or not recipient_wallet_id.isdigit():
                raise ValueError("Recipient registered number must be a valid 10-digit number.")
            recipient_numbers = {
                normalize_ghana_number(str(recipient.momo_number or "").strip()),
                normalize_ghana_number(str(recipient.phone_number or "").strip()),
            }
            recipient_numbers = {number for number in recipient_numbers if number}
            if recipient_numbers and recipient_wallet_id not in recipient_numbers:
                raise ValueError("Recipient registered number does not match recipient account.")

            escrow_deal_id = metadata.get("escrow_deal_id")
            if escrow_deal_id is None:
                raise ValueError("Escrow deal reference is required for release.")
            try:
                escrow_deal_id_int = int(escrow_deal_id)
            except (TypeError, ValueError):
                raise ValueError("Escrow deal reference is invalid.")

            deal_result = await self.db.execute(
                select(Transaction).filter(
                    Transaction.id == escrow_deal_id_int,
                    Transaction.user_id == wallet.user_id,
                    Transaction.type == TransactionType.ESCROW_CREATE,
                )
            )
            deal_tx = deal_result.scalars().first()
            if not deal_tx:
                raise ValueError("Escrow deal not found for release.")

            deal_metadata = _parse_metadata_json(deal_tx.metadata_json)
            deal_status = str(deal_metadata.get("deal_status", "active")).strip().lower()
            if deal_status != "active":
                raise ValueError(f"Escrow deal is not releasable. Current status: {deal_status}.")

            expected_recipient = deal_metadata.get("recipient_id")
            try:
                expected_recipient_int = int(expected_recipient)
            except (TypeError, ValueError):
                raise ValueError("Escrow deal recipient is invalid.")
            if expected_recipient_int != recipient_id_int:
                raise ValueError("Escrow release recipient does not match the original deal recipient.")

            if abs(float(deal_tx.amount or 0.0) - float(amount)) > 1e-9:
                raise ValueError("Escrow release amount must match the original deal amount.")

    async def _run_pre_validation_checks(
        self,
        user_id: int,
        tx_type: str,
        amount: float,
        metadata: Dict[str, Any],
        agent_id: Optional[int],
    ):
        sensitive_types = {
            TransactionType.TRANSFER,
            TransactionType.AGENT_WITHDRAWAL,
            TransactionType.BTC_WITHDRAW,
            TransactionType.CARD_SPEND,
            TransactionType.ESCROW_CREATE,
            TransactionType.ESCROW_RELEASE,
            TransactionType.INVESTMENT_CREATE,
            TransactionType.INVESTMENT_PAYOUT,
        }

        if tx_type in sensitive_types and not metadata.get("pin_verified", False):
            raise ValueError("Transaction PIN verification required.")

        if tx_type == TransactionType.ESCROW_CREATE:
            recipient_id = metadata.get("recipient_id")
            try:
                recipient_id_int = int(recipient_id)
            except (TypeError, ValueError):
                raise ValueError("Recipient user ID is invalid.")
            recipient_wallet_id = normalize_ghana_number(str(metadata.get("recipient_wallet_id", "")).strip())
            if not recipient_wallet_id:
                raise ValueError("Recipient registered number is required for escrow deal creation.")
            if len(recipient_wallet_id) != 10 or not recipient_wallet_id.isdigit():
                raise ValueError("Recipient registered number must be a valid 10-digit number.")
            recipient_result = await self.db.execute(select(User).filter(User.id == recipient_id_int))
            recipient = recipient_result.scalars().first()
            if not recipient or not recipient.is_active or not recipient.is_verified:
                raise ValueError("Recipient user not found, inactive, or unverified.")
            recipient_numbers = {
                normalize_ghana_number(str(recipient.momo_number or "").strip()),
                normalize_ghana_number(str(recipient.phone_number or "").strip()),
            }
            recipient_numbers = {number for number in recipient_numbers if number}
            if recipient_numbers and recipient_wallet_id not in recipient_numbers:
                raise ValueError("Recipient registered number does not match recipient account.")

        biometric_threshold = float(metadata.get("biometric_threshold", 2500.0))
        if amount >= biometric_threshold and not metadata.get("biometric_verified", False):
            raise ValueError("Biometric verification required for high-value transaction.")

        start_of_day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        total_today_query = await self.db.execute(
            select(func.coalesce(func.sum(func.abs(Transaction.amount)), 0.0)).filter(
                Transaction.user_id == user_id,
                Transaction.status.in_(["pending", "completed"]),
                Transaction.timestamp >= start_of_day,
            )
        )
        total_today = float(total_today_query.scalar_one() or 0.0)
        daily_limit = float(metadata.get("daily_limit", 10000.0))
        if tx_type in {TransactionType.INVESTMENT_CREATE, TransactionType.INVESTMENT_PAYOUT}:
            # Investments are intentionally uncapped by the generic daily limit so users/agents
            # can move any available wallet principal into investment plans.
            daily_limit = max(daily_limit, total_today + abs(amount))
        if total_today + abs(amount) > daily_limit:
            raise ValueError(f"Daily transaction limit exceeded. Limit: {daily_limit}")

        risk_score = 0
        if not metadata.get("device_fingerprint"):
            risk_score += 20
        if not metadata.get("ip_address"):
            risk_score += 10
        if amount > 2000:
            risk_score += 20
        if tx_type in {TransactionType.BTC_WITHDRAW, TransactionType.CARD_SPEND, TransactionType.AGENT_WITHDRAWAL}:
            risk_score += 15
        if metadata.get("channel", "").upper() == "USSD" and amount > 1000:
            risk_score += 15

        if agent_id and risk_score >= 60:
            self.db.add(
                RiskEvent(
                    agent_id=agent_id,
                    event_type="high_risk_transaction",
                    severity="high" if risk_score < 80 else "critical",
                    description=f"Risk score {risk_score} for {tx_type} amount {amount}",
                )
            )
            await self.db.flush()

        if risk_score >= 80 and not metadata.get("risk_override", False):
            raise ValueError("Transaction blocked by AML/risk controls.")

    async def _generate_ledger_entries(
        self, 
        transaction: Transaction, 
        wallet: Wallet, 
        agent_id: Optional[int],
        metadata: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        metadata = metadata or {}
        entries = []
        tx_type = transaction.type
        amount = transaction.amount
        fee = metadata.get("fee", 0.0)
        net_amount = amount - fee # For receiver logic if applicable

        # --- AGENT TRANSACTIONS ---
        if tx_type == TransactionType.AGENT_DEPOSIT:
            # Agent Float (Liability) DECREASES -> Debit
            # Customer Wallet (Liability) INCREASES -> Credit
            entries.append({"account_name": "Agent Float (Liability)", "debit": amount})
            entries.append({"account_name": "Customer Wallets (Liability)", "credit": amount})
            
            # Commission
            commission = metadata.get("commission", 0.0)
            if commission > 0:
                entries.append({"account_name": "Commissions Expense", "debit": commission})
                entries.append({"account_name": "Commissions Payable (Liability)", "credit": commission})

        elif tx_type == TransactionType.AGENT_WITHDRAWAL:
            # Customer Wallet (Liability) DECREASES -> Debit
            # Agent Float (Liability) INCREASES -> Credit
            # Revenue (Fee) -> Credit
            total_deduction = amount + fee
            entries.append({"account_name": "Customer Wallets (Liability)", "debit": total_deduction})
            entries.append({"account_name": "Agent Float (Liability)", "credit": amount})
            
            if fee > 0:
                entries.append({"account_name": "Revenue - Transaction Fees", "credit": fee})
            
            commission = metadata.get("commission", 0.0)
            if commission > 0:
                 entries.append({"account_name": "Commissions Expense", "debit": commission})
                 entries.append({"account_name": "Commissions Payable (Liability)", "credit": commission})

        # --- WALLET TRANSACTIONS ---
        elif tx_type == TransactionType.TRANSFER:
            receiver_user_id = metadata.get("receiver_id")
            entries.append({"account_name": "Customer Wallets (Liability)", "debit": amount, "description": f"P2P Send to {receiver_user_id}"})
            entries.append({"account_name": "Customer Wallets (Liability)", "credit": amount, "description": f"P2P Receive from {transaction.user_id}"})
            # Note: Fee logic for P2P is usually sender pays fee on top, or fee is deducted. 
            # If fee exists:
            if fee > 0:
                 # Adjust sender debit if fee is ON TOP of amount
                 # Or if amount includes fee. Assuming amount is transfer amount, fee is extra.
                 entries[0]["debit"] += fee
                 entries.append({"account_name": "Revenue - Transaction Fees", "credit": fee})

        elif tx_type == TransactionType.FUNDING:
            entries.append({"account_name": "Cash (External Bank)", "debit": amount})
            entries.append({"account_name": "Customer Wallets (Liability)", "credit": amount})

        elif tx_type in [TransactionType.AIRTIME, TransactionType.DATA]:
            cost = metadata.get("cost_price", amount * 0.95) # Assume 5% margin if not specified
            margin = amount - cost
            entries.append({"account_name": "Customer Wallets (Liability)", "debit": amount})
            entries.append({"account_name": "Cash (External Bank)", "credit": cost}) # We pay provider
            if margin > 0:
                entries.append({"account_name": "Revenue - Airtime Margins", "credit": margin})

        # --- LOANS ---
        elif tx_type == TransactionType.LOAN_DISBURSE:
            entries.append({"account_name": "Loan Principal (Asset)", "debit": amount})
            entries.append({"account_name": "Customer Wallets (Liability)", "credit": amount})

        elif tx_type == TransactionType.LOAN_REPAY:
            interest = metadata.get("interest_amount", 0.0)
            principal_repayment = amount - interest
            entries.append({"account_name": "Customer Wallets (Liability)", "debit": amount})
            entries.append({"account_name": "Loan Principal (Asset)", "credit": principal_repayment})
            if interest > 0:
                entries.append({"account_name": "Revenue - Loan Interest", "credit": interest})

        # --- ESCROW ---
        elif tx_type == TransactionType.ESCROW_CREATE:
            entries.append({"account_name": "Customer Wallets (Liability)", "debit": amount + fee})
            entries.append({"account_name": "Customer Escrow (Liability)", "credit": amount})
            if fee > 0:
                entries.append({"account_name": "Revenue - Transaction Fees", "credit": fee})

        elif tx_type == TransactionType.ESCROW_RELEASE:
            recipient_id = metadata.get("recipient_id", transaction.user_id)
            receiver_net_amount = amount - fee
            if receiver_net_amount < 0:
                raise ValueError("Escrow release fee cannot exceed release amount.")
            entries.append({"account_name": "Customer Escrow (Liability)", "debit": amount})
            entries.append(
                {
                    "account_name": "Customer Wallets (Liability)",
                    "credit": receiver_net_amount,
                    "description": f"Escrow Release to {recipient_id} (net of receiver fee)",
                }
            )
            if fee > 0:
                entries.append({"account_name": "Revenue - Transaction Fees", "credit": fee})

        # --- INVESTMENTS ---
        elif tx_type == TransactionType.INVESTMENT_CREATE:
            entries.append({"account_name": "Customer Wallets (Liability)", "debit": amount})
            entries.append({"account_name": "Customer Investments (Liability)", "credit": amount})

        elif tx_type == TransactionType.INVESTMENT_PAYOUT:
            net_profit = float(metadata.get("gain", 0.0) or 0.0)
            gross_profit = float(metadata.get("gross_profit", net_profit) or net_profit)
            profit_fee = float(metadata.get("fee", 0.0) or 0.0)
            total_payout = amount + net_profit
            entries.append({"account_name": "Customer Investments (Liability)", "debit": amount}) # Principal
            if gross_profit > 0:
                entries.append({"account_name": "Investment Payout (Expense)", "debit": gross_profit})
            if profit_fee > 0:
                entries.append({"account_name": "Revenue - Investment Management Fees", "credit": profit_fee})
            entries.append({"account_name": "Customer Wallets (Liability)", "credit": total_payout})

        # --- VIRTUAL CARDS ---
        elif tx_type == TransactionType.CARD_LOAD:
            # Move from Wallet to Card (which is just another liability bucket usually, or prepaid expense)
            # We'll treat Virtual Card Balance as a separate Liability sub-account type conceptually,
            # or just map it to "Customer Wallets (Liability)" but track it in `VirtualCard` model.
            # To be precise, let's assume we have a "Customer Virtual Cards (Liability)" account or similar.
            # For now, we'll map it to "Customer Wallets (Liability)" debit and "Cash (External Bank)" credit? 
            # NO, Virtual Card is usually pre-funded at a provider.
            # When user loads card -> We move funds from User Wallet to Provider.
            # So: Debit Customer Wallet, Credit Cash (External Bank) [sent to provider].
            # AND we update the Virtual Card Balance in our DB to reflect this.
            entries.append({"account_name": "Customer Wallets (Liability)", "debit": amount})
            entries.append({"account_name": "Cash (External Bank)", "credit": amount}) 
            if fee > 0:
                entries.append({"account_name": "Customer Wallets (Liability)", "debit": fee})
                entries.append({"account_name": "Revenue - Transaction Fees", "credit": fee})

        elif tx_type == TransactionType.CARD_WITHDRAW:
             # Unload card back to wallet
             entries.append({"account_name": "Cash (External Bank)", "debit": amount}) # Receive refund from provider
             entries.append({"account_name": "Customer Wallets (Liability)", "credit": amount})

        elif tx_type == TransactionType.CARD_SPEND:
            fx_margin = float(metadata.get("fx_margin", 0.0))
            total_spend = amount + fee + fx_margin
            entries.append({"account_name": "Customer Wallets (Liability)", "debit": total_spend})
            entries.append({"account_name": "Cash (External Bank)", "credit": amount})
            if fee > 0:
                entries.append({"account_name": "Revenue - Transaction Fees", "credit": fee})
            if fx_margin > 0:
                entries.append({"account_name": "Revenue - FX Margins", "credit": fx_margin})

        # --- CRYPTO ---
        elif tx_type == TransactionType.BTC_DEPOSIT:
            # Asset: Crypto Hot Wallet INCREASES -> Debit
            # Liability: Customer Crypto Balances INCREASES -> Credit
            entries.append({"account_name": "Crypto Hot Wallet (Asset)", "debit": amount})
            entries.append({"account_name": "Customer Crypto Balances (Liability)", "credit": amount})

        elif tx_type == TransactionType.BTC_WITHDRAW:
            # Liability: Customer Crypto Balances DECREASES -> Debit
            # Asset: Crypto Hot Wallet DECREASES -> Credit
            # Fee logic
            entries.append({"account_name": "Customer Crypto Balances (Liability)", "debit": amount + fee})
            entries.append({"account_name": "Crypto Hot Wallet (Asset)", "credit": amount})
            if fee > 0:
                entries.append({"account_name": "Revenue - Transaction Fees", "credit": fee})

        return entries

    async def _update_wallet_balances(self, transaction: Transaction, wallet: Wallet, agent_id: Optional[int], metadata: Optional[Dict[str, Any]] = None):
        metadata = metadata or {}
        tx_type = transaction.type
        amount = transaction.amount
        fee = metadata.get("fee", 0.0)
        
        # --- AGENT ---
        if tx_type == TransactionType.AGENT_DEPOSIT:
            wallet.balance += amount
            if agent_id:
                agent = await self._get_agent(agent_id)
                agent.float_balance -= amount
                commission = metadata.get("commission", 0.0)
                if commission > 0:
                    agent.commission_balance += commission
        
        elif tx_type == TransactionType.AGENT_WITHDRAWAL:
            wallet.balance -= (amount + fee)
            if agent_id:
                agent = await self._get_agent(agent_id)
                agent.float_balance += amount
                commission = metadata.get("commission", 0.0)
                if commission > 0:
                    agent.commission_balance += commission

        # --- WALLET ---
        elif tx_type == TransactionType.TRANSFER:
            wallet.balance -= (amount + fee)
            receiver_id = metadata.get("receiver_id")
            result = await self.db.execute(select(Wallet).filter(Wallet.user_id == receiver_id))
            receiver_wallet = result.scalars().first()
            if receiver_wallet:
                receiver_wallet.balance += amount

        elif tx_type == TransactionType.FUNDING:
            wallet.balance += amount

        elif tx_type in [TransactionType.AIRTIME, TransactionType.DATA]:
            wallet.balance -= amount

        elif tx_type == TransactionType.LOAN_DISBURSE:
            loan_balance_increase = float(metadata.get("wallet_loan_balance_increase", amount) or amount)
            wallet.balance += amount
            wallet.loan_balance += loan_balance_increase

        elif tx_type == TransactionType.LOAN_REPAY:
            wallet.balance -= amount
            wallet.loan_balance -= amount
            if wallet.loan_balance < 0: wallet.loan_balance = 0

        elif tx_type == TransactionType.ESCROW_CREATE:
            wallet.balance -= (amount + fee)
            wallet.escrow_balance += amount

        elif tx_type == TransactionType.ESCROW_RELEASE:
            receiver_net_amount = amount - fee
            if receiver_net_amount < 0:
                raise ValueError("Escrow release fee cannot exceed release amount.")
            wallet.escrow_balance -= amount
            recipient_id = metadata.get("recipient_id")
            if recipient_id and recipient_id != wallet.user_id:
                recipient_wallet = await self._get_wallet(int(recipient_id))
                recipient_wallet.balance += receiver_net_amount
            else:
                 wallet.balance += receiver_net_amount # Release back to self (net of receiver fee)

        elif tx_type == TransactionType.INVESTMENT_CREATE:
            wallet.balance -= amount
            wallet.investment_balance += amount

        elif tx_type == TransactionType.INVESTMENT_PAYOUT:
            wallet.investment_balance -= amount
            gain = metadata.get("gain", 0.0)
            wallet.balance += (amount + gain)

        # --- VIRTUAL CARD ---
        elif tx_type == TransactionType.CARD_LOAD:
            wallet.balance -= (amount + fee)
            card_id = metadata.get("card_id") # Optional specific card
            card = await self._get_virtual_card(wallet.user_id, card_id)
            card.balance += amount
            self.db.add(card)

        elif tx_type == TransactionType.CARD_WITHDRAW:
            card_id = metadata.get("card_id")
            card = await self._get_virtual_card(wallet.user_id, card_id)
            if card.balance < amount:
                 raise ValueError("Insufficient Virtual Card balance")
            card.balance -= amount
            wallet.balance += amount
            self.db.add(card)

        elif tx_type == TransactionType.CARD_SPEND:
            fx_margin = float(metadata.get("fx_margin", 0.0))
            wallet.balance -= (amount + fee + fx_margin)
            card_id = metadata.get("card_id")
            if card_id and metadata.get("use_card_balance", False):
                card = await self._get_virtual_card(wallet.user_id, card_id)
                if card.balance < amount:
                    raise ValueError("Insufficient Virtual Card balance")
                card.balance -= amount
                self.db.add(card)

        # --- CRYPTO ---
        elif tx_type == TransactionType.BTC_DEPOSIT:
            coin_type = metadata.get("coin_type")
            crypto_wallet = await self._get_crypto_wallet(wallet.user_id, coin_type)
            crypto_wallet.balance += amount
            self.db.add(crypto_wallet)

        elif tx_type == TransactionType.BTC_WITHDRAW:
            coin_type = metadata.get("coin_type")
            crypto_wallet = await self._get_crypto_wallet(wallet.user_id, coin_type)
            crypto_wallet.balance -= (amount + fee) # Fee is usually taken from crypto balance in this model
            self.db.add(crypto_wallet)

        self.db.add(wallet)

    async def _send_notification(self, user_id: int, message: str):
        """
        Placeholder for Real-Time Notification System (Firebase/Socket.io/SMS).
        """
        # In a real app, this would trigger an async task to send Push/SMS
        logger.info(f"NOTIFICATION to User {user_id}: {message}")

# Dependency Injection Helper
async def get_transaction_engine(
    db: AsyncSession = Depends(get_db),
    ledger_service: LedgerService = Depends(get_ledger_service)
) -> TransactionEngine:
    return TransactionEngine(db, ledger_service)
