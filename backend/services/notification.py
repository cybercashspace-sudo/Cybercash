from collections.abc import Iterable
from typing import Sequence

from backend.models.user import User
from backend.services.sms_service import get_sms_service


class NotificationService:
    def __init__(self):
        self.sms_service = get_sms_service()

    async def send_sms(self, phone: str, message: str, sms_type: str | None = None) -> dict:
        return self.sms_service.send_sms(phone, message, sms_type=sms_type)

    async def send_bulk_sms(
        self,
        recipients: Sequence[str] | Iterable[str],
        message: str,
        sms_type: str | None = None,
        is_schedule: bool = False,
        schedule_date: str = "",
    ) -> dict:
        return self.sms_service.send_bulk_sms(
            recipients,
            message,
            sms_type=sms_type,
            is_schedule=is_schedule,
            schedule_date=schedule_date,
        )

    async def send_to_users(
        self,
        users: Sequence[User] | Iterable[User],
        message: str,
        sms_type: str | None = None,
        is_schedule: bool = False,
        schedule_date: str = "",
    ) -> dict:
        recipients: list[str] = []
        for user in users:
            number = str(getattr(user, "momo_number", "") or getattr(user, "phone_number", "") or "").strip()
            if number:
                recipients.append(number)
        return await self.send_bulk_sms(
            recipients,
            message,
            sms_type=sms_type,
            is_schedule=is_schedule,
            schedule_date=schedule_date,
        )
