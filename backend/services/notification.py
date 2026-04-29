from backend.services.sms_service import get_sms_service


class NotificationService:
    def __init__(self):
        self.sms_service = get_sms_service()

    async def send_sms(self, phone: str, message: str, sms_type: str | None = None) -> dict:
        return self.sms_service.send_sms(phone, message, sms_type=sms_type)
