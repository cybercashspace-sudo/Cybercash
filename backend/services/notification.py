import html
import logging
import re
from collections.abc import Iterable
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.mailer import send_email
from backend.models.user import User


logger = logging.getLogger(__name__)


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
