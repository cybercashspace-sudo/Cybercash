import logging
import os
from typing import Any, Optional

import requests

from utils.network import normalize_ghana_number


logger = logging.getLogger(__name__)


class SMSService:
    def __init__(self):
        self.env = str(os.getenv("ENV", "development") or "development").strip().lower()
        self.is_production = self.env in {"prod", "production"}
        self.provider = (os.getenv("SMS_PROVIDER") or os.getenv("OTP_PROVIDER") or "mnotify").lower()
        if not self.is_production and self.provider not in {"log", "simulated"}:
            logger.info("SMS provider %s disabled outside production; using log fallback.", self.provider)
            self.provider = "log"
        self.mnotify_api_key = os.getenv("MNOTIFY_API_KEY", "")
        self.sender_id = (
            os.getenv("SMS_SENDER_ID")
            or os.getenv("MNOTIFY_SENDER")
            or "CyberCash"
        ).strip() or "CyberCash"
        self.mnotify_sender = self.sender_id
        self.mnotify_endpoint = os.getenv("MNOTIFY_SMS_URL", "https://api.mnotify.com/api/sms/quick")

    def format_recipient(self, phone: str, provider: Optional[str] = None) -> str:
        provider = (provider or self.provider or "mnotify").lower()
        normalized = normalize_ghana_number(phone or "")
        digits = "".join(ch for ch in normalized if ch.isdigit())
        if not digits:
            return ""
        if len(digits) == 10 and digits.startswith("0"):
            digits = f"233{digits[1:]}"
        elif digits.startswith("233") and len(digits) == 12:
            digits = digits
        if provider == "twilio":
            if not digits.startswith("+"):
                digits = f"+{digits}"
        return digits

    def send_sms(
        self,
        phone: str,
        message: str,
        sms_type: Optional[str] = None,
        provider: Optional[str] = None,
        sender_id: Optional[str] = None,
    ) -> dict:
        provider = (provider or self.provider or "mnotify").lower()
        sender_id = (sender_id or self.sender_id or "CyberCash").strip() or "CyberCash"
        recipient = self.format_recipient(phone, provider=provider)
        if not recipient:
            logger.warning("Invalid phone number for SMS: %s", phone)
            return {"status": "error", "provider": provider, "detail": "Invalid phone number"}
        if provider == "mnotify":
            return self._send_mnotify(recipient, message, sms_type=sms_type, sender_id=sender_id)
        if provider == "hubtel":
            return self._send_hubtel(recipient, message, sender_id=sender_id)
        if provider == "arkesel":
            return self._send_arkesel(recipient, message, sender_id=sender_id)
        if provider == "twilio":
            return self._send_twilio(recipient, message, sender_id=sender_id)

        logger.info("SMS (%s) queued for %s using sender %s", provider, recipient, sender_id)
        return {"status": "queued", "provider": provider, "recipient": recipient, "sender_id": sender_id}

    @staticmethod
    def _mnotify_extract_detail(payload: Any) -> str:
        if not isinstance(payload, dict):
            return ""
        for key in ("message", "msg", "detail", "description", "error"):
            value = payload.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""

    @classmethod
    def _mnotify_looks_like_error(cls, payload: Any) -> bool:
        if not isinstance(payload, dict):
            return False
        status_value = str(payload.get("status", "") or "").strip().lower()
        if status_value in {"error", "failed", "failure"}:
            return True
        success_flag = payload.get("success")
        if isinstance(success_flag, bool) and success_flag is False:
            return True
        if payload.get("errors") or payload.get("error"):
            detail = cls._mnotify_extract_detail(payload).lower()
            if detail:
                return True
        detail = cls._mnotify_extract_detail(payload).lower()
        for keyword in ("unauthorized", "forbidden", "invalid", "insufficient", "error", "failed", "failure"):
            if keyword in detail:
                return True
        return False

    def _send_mnotify(self, phone: str, message: str, sms_type: Optional[str] = None, sender_id: Optional[str] = None) -> dict:
        if not self.mnotify_api_key:
            logger.warning("MNOTIFY_API_KEY not configured. SMS not sent.")
            return {
                "status": "error",
                "provider": "mnotify",
                "recipient": phone,
                "detail": "MNOTIFY_API_KEY not configured",
            }

        sender = (sender_id or self.sender_id or "CyberCash").strip() or "CyberCash"
        url = f"{self.mnotify_endpoint}?key={self.mnotify_api_key}"
        payload = {
            "recipient": [phone],
            "sender": sender,
            "message": message,
            "is_schedule": False,
        }
        if sms_type:
            payload["sms_type"] = sms_type

        try:
            response = requests.post(url, json=payload, timeout=10)
            http_status = int(getattr(response, "status_code", 0) or 0)
            try:
                provider_payload: Any = response.json()
            except Exception:
                provider_payload = None

            if not response.ok:
                detail = self._mnotify_extract_detail(provider_payload) or (response.text or "")[:300] or "SMS provider request failed"
                logger.warning("mNotify SMS failed (http=%s) to %s: %s", http_status, phone, detail)
                return {
                    "status": "error",
                    "provider": "mnotify",
                    "recipient": phone,
                    "http_status": http_status,
                    "detail": detail,
                }

            if provider_payload is None:
                logger.warning("mNotify SMS returned non-JSON response (http=%s) to %s", http_status, phone)
                return {
                    "status": "error",
                    "provider": "mnotify",
                    "recipient": phone,
                    "http_status": http_status,
                    "detail": "Invalid SMS provider response",
                    "raw": (response.text or "")[:500],
                }

            if self._mnotify_looks_like_error(provider_payload):
                detail = self._mnotify_extract_detail(provider_payload) or "SMS provider rejected request"
                logger.warning("mNotify SMS rejected (http=%s) to %s: %s", http_status, phone, detail)
                return {
                    "status": "error",
                    "provider": "mnotify",
                    "recipient": phone,
                    "http_status": http_status,
                    "detail": detail,
                    "provider_response": provider_payload,
                }

            logger.info("mNotify SMS queued (http=%s) to %s", http_status, phone)
            return {
                "status": "queued",
                "provider": "mnotify",
                "recipient": phone,
                "sender_id": sender,
                "http_status": http_status,
                "provider_response": provider_payload,
            }
        except Exception as exc:
            logger.warning("mNotify SMS send failed: %s", exc)
            return {"status": "error", "provider": "mnotify", "recipient": phone, "sender_id": sender, "detail": str(exc)}

    def _send_hubtel(self, phone_number: str, message: str, sender_id: Optional[str] = None) -> dict:
        client_id = os.getenv("HUBTEL_CLIENT_ID", "")
        client_secret = os.getenv("HUBTEL_CLIENT_SECRET", "")
        sender = (os.getenv("HUBTEL_SENDER_ID") or sender_id or self.sender_id or "CyberCash").strip() or "CyberCash"
        endpoint = os.getenv(
            "HUBTEL_SMS_URL",
            "https://smsc.hubtel.com/v1/messages/send",
        )
        payload = {
            "From": sender,
            "To": phone_number,
            "Content": message,
        }
        try:
            response = requests.post(endpoint, json=payload, auth=(client_id, client_secret), timeout=8)
            if getattr(response, "ok", False):
                return {
                    "status": "queued",
                    "provider": "hubtel",
                    "recipient": phone_number,
                    "sender_id": sender,
                    "http_status": response.status_code,
                }
            return {
                "status": "error",
                "provider": "hubtel",
                "recipient": phone_number,
                "sender_id": sender,
                "http_status": response.status_code,
                "detail": (response.text or "")[:300],
            }
        except Exception as exc:
            logger.warning("Hubtel SMS send failed: %s", exc)
            return {
                "status": "error",
                "provider": "hubtel",
                "recipient": phone_number,
                "sender_id": sender,
                "detail": str(exc),
            }

    def _send_arkesel(self, phone_number: str, message: str, sender_id: Optional[str] = None) -> dict:
        api_key = os.getenv("ARKESEL_API_KEY", "")
        sender = (os.getenv("ARKESEL_SENDER_ID") or sender_id or self.sender_id or "CyberCash").strip() or "CyberCash"
        endpoint = os.getenv(
            "ARKESEL_SMS_URL",
            "https://sms.arkesel.com/sms/api",
        )
        params = {
            "action": "send-sms",
            "api_key": api_key,
            "to": phone_number,
            "from": sender,
            "sms": message,
        }
        try:
            response = requests.get(endpoint, params=params, timeout=8)
            if getattr(response, "ok", False):
                return {
                    "status": "queued",
                    "provider": "arkesel",
                    "recipient": phone_number,
                    "sender_id": sender,
                    "http_status": response.status_code,
                }
            return {
                "status": "error",
                "provider": "arkesel",
                "recipient": phone_number,
                "sender_id": sender,
                "http_status": response.status_code,
                "detail": (response.text or "")[:300],
            }
        except Exception as exc:
            logger.warning("Arkesel SMS send failed: %s", exc)
            return {
                "status": "error",
                "provider": "arkesel",
                "recipient": phone_number,
                "sender_id": sender,
                "detail": str(exc),
            }

    def _send_twilio(self, phone_number: str, message: str, sender_id: Optional[str] = None) -> dict:
        from twilio.rest import Client

        account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        messaging_service_sid = (os.getenv("TWILIO_MESSAGING_SERVICE_SID", "") or "").strip()
        from_number = (os.getenv("TWILIO_FROM_NUMBER", "") or "").strip()
        sender = (sender_id or self.sender_id or "CyberCash").strip() or "CyberCash"
        try:
            client = Client(account_sid, auth_token)
            message_kwargs = {"body": message, "to": phone_number}
            if messaging_service_sid:
                message_kwargs["messaging_service_sid"] = messaging_service_sid
            elif from_number:
                message_kwargs["from_"] = from_number
            else:
                # Twilio can use an alphanumeric sender in supported regions,
                # so we fall back to the shared brand ID when no number/service SID is set.
                message_kwargs["from_"] = sender

            client.messages.create(**message_kwargs)
            return {
                "status": "queued",
                "provider": "twilio",
                "recipient": phone_number,
                "sender_id": sender,
                "twilio_from": message_kwargs.get("from_"),
                "twilio_messaging_service_sid": messaging_service_sid or None,
            }
        except Exception as exc:
            logger.warning("Twilio SMS send failed: %s", exc)
            return {
                "status": "error",
                "provider": "twilio",
                "recipient": phone_number,
                "sender_id": sender,
                "detail": str(exc),
            }


_sms_service = SMSService()


def get_sms_service() -> SMSService:
    return _sms_service
