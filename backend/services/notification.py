import html
import logging
import re
from collections.abc import Iterable
from decimal import Decimal
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.mailer import send_email
from backend.models.user import User


logger = logging.getLogger(__name__)


def _humanize_transaction_type(value: str | None, *, direction: str | None = None) -> str:
    normalized = str(value or "").strip().lower().replace("_", " ")
    if not normalized and direction:
        normalized = direction
    labels = {
        "funding": "deposit",
        "deposit": "deposit",
        "withdrawal": "withdrawal",
        "withdraw": "withdrawal",
        "transfer": "transfer",
        "transfer sent": "transfer",
        "transfer received": "transfer",
        "airtime": "airtime purchase",
        "data": "data bundle purchase",
        "data bundle": "data bundle purchase",
        "wallet topup": "wallet top up",
        "topup": "wallet top up",
        "agent withdrawal": "agent withdrawal",
    }
    label = labels.get(normalized, normalized or "transaction")
    if direction == "receive" and label == "transfer":
        return "transfer received"
    if direction == "send" and label == "transfer":
        return "transfer sent"
    return label


class NotificationService:
    async def send_to_user(
        self,
        user: User,
        message: str,
        *,
        subject: str = "CyberCash account notification",
    ) -> dict:
        email = str(getattr(user, "email", "") or "").strip().lower()
        if not email or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            logger.warning("Email notification unavailable for user_id=%s: no valid account email", user.id)
            return {
                "status": "error",
                "provider": "email",
                "detail": "A valid account email is required for notifications.",
            }
        result = await send_email(subject, [email], f"<p>{html.escape(str(message))}</p>")
        if result.get("status") != "queued":
            logger.warning(
                "Email notification failed for user_id=%s: %s",
                user.id,
                result.get("detail") or "email transport did not confirm delivery",
            )
        return result

    async def send_transaction_notification(
        self,
        user: User,
        transaction_type: str,
        amount: Decimal | float | int | str,
        *,
        currency: str = "GHS",
        subject: str = "Transaction update",
        direction: str | None = None,
    ) -> dict:
        amount_value = Decimal(str(amount or 0)).quantize(Decimal("0.01"))
        label = _humanize_transaction_type(transaction_type, direction=direction)
        amount_text = f"{currency.upper()} {abs(amount_value):.2f}"
        action = "received" if direction == "receive" else "sent" if direction == "send" else "completed"
        if label == "deposit":
            message = f"CyberCash: Your {label} of {amount_text} was completed successfully."
        elif label == "transfer received":
            message = f"CyberCash: You received {amount_text} via transfer."
        elif label == "transfer sent":
            message = f"CyberCash: Your transfer of {amount_text} was sent successfully."
        elif label == "withdrawal":
            message = f"CyberCash: Your withdrawal of {amount_text} was processed successfully."
        else:
            message = f"CyberCash: Your {label} of {amount_text} was completed successfully."
        if label in {"deposit", "withdrawal", "wallet top up"}:
            message = f"CyberCash: Your {label} of {amount_text} was completed successfully."
        return await self.send_to_user(user, message, subject=subject)

    async def send_to_user_id(
        self,
        db: AsyncSession,
        user_id: int,
        message: str,
        *,
        subject: str = "CyberCash account notification",
    ) -> dict:
        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalars().one_or_none()
        if not user:
            logger.warning("Email notification unavailable: user_id=%s was not found", user_id)
            return {"status": "error", "provider": "email", "detail": "Notification account not found."}
        return await self.send_to_user(user, message, subject=subject)

    async def send_to_users(
        self,
        users: Sequence[User] | Iterable[User],
        message: str,
        *,
        subject: str = "CyberCash account notification",
    ) -> dict:
        unique_users: dict[str, User] = {}
        for user in users:
            email = str(getattr(user, "email", "") or "").strip().lower()
            if email and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                unique_users.setdefault(email, user)

        if not unique_users:
            return {
                "status": "error",
                "provider": "email",
                "detail": "No valid account email recipients.",
            }

        results = [
            await self.send_to_user(user, message, subject=subject)
            for user in unique_users.values()
        ]
        queued = sum(result.get("status") == "queued" for result in results)
        failed = len(results) - queued
        return {
            "status": "queued" if failed == 0 else ("partial" if queued else "error"),
            "provider": "email",
            "recipient_count": len(unique_users),
            "sent_count": queued,
            "failed_count": failed,
        }

    async def send_sms(self, phone: str, message: str, sms_type: str | None = None) -> dict:
        return {
            "status": "error",
            "provider": "email",
            "detail": "SMS notifications are disabled. Use the account email notification flow.",
        }

    async def send_bulk_sms(self, *args, **kwargs) -> dict:
        return {
            "status": "error",
            "provider": "email",
            "detail": "SMS notifications are disabled. Use the account email notification flow.",
        }
