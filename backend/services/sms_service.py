import logging
import os
from typing import Any, Iterable, Optional, Sequence

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

    @staticmethod
    def _digits_only(phone: str) -> str:
        return "".join(ch for ch in str(phone or "") if ch.isdigit())

    def _normalize_for_provider(self, phone: str, provider: Optional[str] = None) -> str:
        """
        Normalize a Ghana mobile number for the target provider.

        MNotify quick SMS expects local Ghana numbers in the 0XXXXXXXXX format.
        Other providers may prefer E.164-like values, so we keep the provider
        specific conversion here instead of forcing one global format.
        """
        provider = (provider or self.provider or "mnotify").lower()
        normalized = normalize_ghana_number(phone or "")
        digits = self._digits_only(normalized)
        if not digits:
            return ""

        # Keep MNotify recipients in the local format shown in the provider docs.
        if provider == "mnotify":
            if len(digits) == 12 and digits.startswith("233"):
                return f"0{digits[3:]}"
            if len(digits) == 10 and digits.startswith("0"):
                return digits
            if len(digits) == 9:
                return f"0{digits}"
            return digits

        # Twilio supports the leading plus sign.
        if provider == "twilio":
            if digits.startswith("0") and len(digits) == 10:
                return f"+233{digits[1:]}"
            if digits.startswith("233") and len(digits) == 12:
                return f"+{digits}"
            if len(digits) == 9:
                return f"+233{digits}"
            return f"+{digits}" if not digits.startswith("+") else digits

        # Hubtel/Arkesel and similar providers generally accept the Ghana local format.
        if len(digits) == 12 and digits.startswith("233"):
            return f"0{digits[3:]}"
        if len(digits) == 9:
            return f"0{digits}"
        return digits

    def format_recipient(self, phone: str, provider: Optional[str] = None) -> str:
        return self._normalize_for_provider(phone, provider=provider)

    def _normalize_recipients(
        self,
        recipients: str | Sequence[str] | Iterable[str],
        provider: Optional[str] = None,
    ) -> list[str]:
        if isinstance(recipients, str):
            candidates = [recipients]
        else:
            candidates = list(recipients)

        seen: set[str] = set()
        normalized_recipients: list[str] = []
        for candidate in candidates:
            normalized = self.format_recipient(str(candidate or ""), provider=provider)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            normalized_recipients.append(normalized)
        return normalized_recipients

    def send_sms(
        self,
        phone: str,
        message: str,
        sms_type: Optional[str] = None,
        provider: Optional[str] = None,
        sender_id: Optional[str] = None,
        is_schedule: bool = False,
        schedule_date: str = "",
    ) -> dict:
        provider = (provider or self.provider or "mnotify").lower()
        sender_id = (sender_id or self.sender_id or "CyberCash").strip() or "CyberCash"
        recipients = self._normalize_recipients([phone], provider=provider)
        if not recipients:
            logger.warning("Invalid phone number for SMS: %s", phone)
            return {"status": "error", "provider": provider, "detail": "Invalid phone number"}
        if provider == "mnotify":
            return self._send_mnotify(
                recipients,
                message,
                sms_type=sms_type,
                sender_id=sender_id,
                is_schedule=is_schedule,
                schedule_date=schedule_date,
            )
        if provider == "hubtel":
            return self._send_hubtel(recipients[0], message, sender_id=sender_id)
        if provider == "arkesel":
            return self._send_arkesel(recipients[0], message, sender_id=sender_id)
        if provider == "twilio":
            return self._send_twilio(recipients[0], message, sender_id=sender_id)

        logger.info("SMS (%s) queued for %s using sender %s", provider, recipients[0], sender_id)
        return {"status": "queued", "provider": provider, "recipient": recipients[0], "sender_id": sender_id}

    def send_bulk_sms(
        self,
        recipients: str | Sequence[str] | Iterable[str],
        message: str,
        sms_type: Optional[str] = None,
        provider: Optional[str] = None,
        sender_id: Optional[str] = None,
        is_schedule: bool = False,
        schedule_date: str = "",
    ) -> dict:
        provider = (provider or self.provider or "mnotify").lower()
        normalized_recipients = self._normalize_recipients(recipients, provider=provider)
        if not normalized_recipients:
            return {"status": "error", "provider": provider, "detail": "No valid recipient numbers"}

        if provider == "mnotify":
            return self._send_mnotify(
                normalized_recipients,
                message,
                sms_type=sms_type,
                sender_id=sender_id,
                is_schedule=is_schedule,
                schedule_date=schedule_date,
            )

        results = [
            self.send_sms(
                recipient,
                message,
                sms_type=sms_type,
                provider=provider,
                sender_id=sender_id,
                is_schedule=is_schedule,
                schedule_date=schedule_date,
            )
            for recipient in normalized_recipients
        ]
        queued = [result for result in results if str(result.get("status", "")).lower() == "queued"]
        errors = [result for result in results if str(result.get("status", "")).lower() == "error"]
        return {
            "status": "queued" if queued and not errors else ("partial" if queued else "error"),
            "provider": provider,
            "recipients": normalized_recipients,
            "results": results,
        }

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

    def _send_mnotify(
        self,
        recipients: Sequence[str],
        message: str,
        sms_type: Optional[str] = None,
        sender_id: Optional[str] = None,
        is_schedule: bool = False,
        schedule_date: str = "",
    ) -> dict:
        if not self.mnotify_api_key:
            logger.warning("MNOTIFY_API_KEY not configured. SMS not sent.")
            return {
                "status": "error",
                "provider": "mnotify",
                "recipient": list(recipients),
                "detail": "MNOTIFY_API_KEY not configured",
            }

        sender = (sender_id or self.sender_id or "CyberCash").strip() or "CyberCash"
        url = f"{self.mnotify_endpoint}?key={self.mnotify_api_key}"
        payload = {
            "recipient": list(recipients),
            "sender": sender,
            "message": message,
            "is_schedule": bool(is_schedule),
            "schedule_date": schedule_date or "",
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
                logger.warning("mNotify SMS failed (http=%s) to %s: %s", http_status, ",".join(recipients), detail)
                return {
                    "status": "error",
                    "provider": "mnotify",
                    "recipient": list(recipients),
                    "http_status": http_status,
                    "detail": detail,
                }

            if provider_payload is None:
                logger.warning("mNotify SMS returned non-JSON response (http=%s) to %s", http_status, ",".join(recipients))
                return {
                    "status": "error",
                    "provider": "mnotify",
                    "recipient": list(recipients),
                    "http_status": http_status,
                    "detail": "Invalid SMS provider response",
                    "raw": (response.text or "")[:500],
                }

            if self._mnotify_looks_like_error(provider_payload):
                detail = self._mnotify_extract_detail(provider_payload) or "SMS provider rejected request"
                logger.warning("mNotify SMS rejected (http=%s) to %s: %s", http_status, ",".join(recipients), detail)
                return {
                    "status": "error",
                    "provider": "mnotify",
                    "recipient": list(recipients),
                    "http_status": http_status,
                    "detail": detail,
                    "provider_response": provider_payload,
                }

            logger.info("mNotify SMS queued (http=%s) to %s", http_status, ",".join(recipients))
            return {
                "status": "queued",
                "provider": "mnotify",
                "recipient": list(recipients),
                "sender_id": sender,
                "http_status": http_status,
                "provider_response": provider_payload,
            }
        except Exception as exc:
            logger.warning("mNotify SMS send failed: %s", exc)
            return {"status": "error", "provider": "mnotify", "recipient": list(recipients), "sender_id": sender, "detail": str(exc)}

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
