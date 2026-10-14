import logging
import re
from typing import List

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema
from pydantic import EmailStr

from backend.core.config import settings

logger = logging.getLogger(__name__)

def _connection_config() -> ConnectionConfig:
    return ConnectionConfig(
        MAIL_USERNAME=settings.MAIL_USERNAME,
        MAIL_PASSWORD=settings.MAIL_PASSWORD,
        MAIL_FROM=settings.MAIL_FROM,
        MAIL_PORT=settings.MAIL_PORT,
        MAIL_SERVER=settings.MAIL_SERVER,
        MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
        MAIL_STARTTLS=True,
        MAIL_SSL_TLS=False,
        USE_CREDENTIALS=True,
    )


async def send_email(subject: str, recipients: List[EmailStr], body: str) -> dict:
    recipient_list = []
    seen = set()
    for recipient in recipients:
        normalized = str(recipient or "").strip().lower()
        if not normalized or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
            continue
        if normalized not in seen:
            seen.add(normalized)
            recipient_list.append(normalized)
    if not recipient_list:
        return {"status": "error", "provider": "email", "detail": "No email recipient provided."}

    if not all((settings.MAIL_USERNAME, settings.MAIL_PASSWORD, settings.MAIL_FROM, settings.MAIL_SERVER)):
        return {"status": "error", "provider": "email", "detail": "Email delivery is not configured."}

    try:
        message = MessageSchema(
            subject=subject,
            recipients=recipient_list,
            body=body,
            subtype="html",
        )

        fm = FastMail(_connection_config())
        await fm.send_message(message)
        return {"status": "queued", "provider": "email", "recipients": recipient_list}
    except Exception as exc:
        logger.exception("Email delivery failed (subject=%s, recipient_count=%s)", subject, len(recipient_list))
        return {"status": "error", "provider": "email", "detail": "Email delivery failed."}
