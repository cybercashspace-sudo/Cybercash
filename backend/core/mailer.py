from typing import List

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema
from pydantic import EmailStr

from backend.core.config import settings

conf = ConnectionConfig(
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
    recipient_list = [str(recipient).strip() for recipient in recipients if str(recipient).strip()]
    if not recipient_list:
        return {"status": "error", "provider": "email", "detail": "No email recipient provided."}

    try:
        if settings.ENV == "development":
            print("====== EMAIL DEBUG ======")
            print("To:", recipient_list)
            print("Subject:", subject)
            print("Body:", body)
            print("=========================")
            return {"status": "queued", "provider": "email", "recipients": recipient_list}

        message = MessageSchema(
            subject=subject,
            recipients=recipient_list,
            body=body,
            subtype="html",
        )

        fm = FastMail(conf)
        await fm.send_message(message)
        return {"status": "queued", "provider": "email", "recipients": recipient_list}
    except Exception as exc:
        print(f"CRITICAL ERROR in send_email: {exc}")
        return {"status": "error", "provider": "email", "detail": str(exc)}
