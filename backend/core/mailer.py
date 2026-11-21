import logging
import re
import asyncio
from email.utils import formataddr
import uuid
from typing import List

import httpx
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema
from pydantic import EmailStr

from backend.core.config import settings

logger = logging.getLogger(__name__)
_RESEND_API_URL = "https://api.resend.com/emails"
_RESEND_MAX_ATTEMPTS = 2


async def _send_with_resend(subject: str, recipients: list[str], body: str) -> dict:
    sender_email = str(settings.MAIL_FROM or "").strip()
    sender_name = str(settings.MAIL_FROM_NAME or "CyberCash").strip()
    sender = formataddr((sender_name, sender_email)) if sender_name else sender_email
    payload = {
        "from": sender,
        "to": recipients,
        "subject": subject,
        "html": body,
    }
    # Reuse one key across retries so a timeout cannot create duplicate messages.
    headers = {
        "Authorization": f"Bearer {settings.RESEND_API_KEY}",
        "Content-Type": "application/json",
        "Idempotency-Key": str(uuid.uuid4()),
    }
    # Keep the user-facing OTP request bounded even when the provider is slow.
    timeout = httpx.Timeout(min(settings.MAIL_TIMEOUT_SECONDS, 5))

    for attempt in range(_RESEND_MAX_ATTEMPTS):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(_RESEND_API_URL, json=payload, headers=headers)
            if response.is_success:
                return {"status": "queued", "provider": "resend"}
            if response.status_code not in {408, 429} and response.status_code < 500:
                logger.warning("Email provider rejected a message (status_code=%s)", response.status_code)
                return {"status": "error", "provider": "email", "detail": "Email is temporarily unavailable. Please try again shortly."}
            logger.warning("Email provider temporarily unavailable (status_code=%s)", response.status_code)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            logger.warning("Email provider request failed (error_type=%s)", type(exc).__name__)

        if attempt + 1 < _RESEND_MAX_ATTEMPTS:
            await asyncio.sleep(0.2)

    return {"status": "error", "provider": "email", "detail": "Email is temporarily unavailable. Please try again shortly."}

def _connection_config() -> ConnectionConfig:
    mail_password = settings.MAIL_PASSWORD
    if str(settings.MAIL_SERVER or "").strip().lower() == "smtp.gmail.com":
        if hasattr(mail_password, "get_secret_value"):
            mail_password = mail_password.get_secret_value()
        # Google displays app passwords in groups; SMTP expects the raw code.
        mail_password = "".join(str(mail_password or "").split())

    return ConnectionConfig(
        MAIL_USERNAME=settings.MAIL_USERNAME,
        MAIL_PASSWORD=mail_password,
        MAIL_FROM=settings.MAIL_FROM,
        MAIL_PORT=settings.MAIL_PORT,
        MAIL_SERVER=settings.MAIL_SERVER,
        MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
        MAIL_STARTTLS=True,
        MAIL_SSL_TLS=False,
        USE_CREDENTIALS=True,
        TIMEOUT=settings.MAIL_TIMEOUT_SECONDS,
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

    if settings.MAIL_PROVIDER == "resend" and not (settings.RESEND_API_KEY and settings.MAIL_FROM):
        logger.error("Resend email provider is selected but its required settings are missing.")
        return {
            "status": "error",
            "provider": "email",
            "detail": "Email is temporarily unavailable. Please try again shortly.",
        }

    if settings.RESEND_API_KEY and settings.MAIL_FROM:
        try:
            return await _send_with_resend(subject, recipient_list, body)
        except Exception as exc:
            logger.warning("Email provider request failed (error_type=%s)", type(exc).__name__)
            return {"status": "error", "provider": "email", "detail": "Email is temporarily unavailable. Please try again shortly."}

    if not all((settings.MAIL_USERNAME, settings.MAIL_PASSWORD, settings.MAIL_FROM, settings.MAIL_SERVER)):
        return {"status": "error", "provider": "email", "detail": "Email is temporarily unavailable. Please try again shortly."}

    try:
        message = MessageSchema(
            subject=subject,
            recipients=recipient_list,
            body=body,
            subtype="html",
        )

        fm = FastMail(_connection_config())
        await fm.send_message(message)
        return {"status": "queued", "provider": "email"}
    except Exception as exc:
        logger.warning(
            "Email delivery failed (subject=%s, recipient_count=%s, error_type=%s)",
            subject,
            len(recipient_list),
            type(exc).__name__,
        )
        return {"status": "error", "provider": "email", "detail": "Email is temporarily unavailable. Please try again shortly."}
