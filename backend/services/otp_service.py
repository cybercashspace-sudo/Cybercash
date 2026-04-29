import json
import logging
import os
import random
import re
import time
from typing import Optional

import requests
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from backend.core.security import hash_password, verify_password
from backend.services.hubtel_otp import HubtelOTPClient
from backend.services.sms_service import get_sms_service

logger = logging.getLogger(__name__)


def generate_otp():
    return str(random.randint(100000, 999999))


def _allow_external_sms_in_dev() -> bool:
    return str(os.getenv("ALLOW_EXTERNAL_SMS_IN_DEV", "")).strip().lower() in {"1", "true", "yes", "on"}


def _is_valid_email(value: str | None) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", str(value or "").strip()))


class OTPService:
    def __init__(self, provider: str | None = None, hubtel_client: HubtelOTPClient | None = None):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.redis_connect_timeout_seconds = float(os.getenv("REDIS_CONNECT_TIMEOUT_SECONDS", "2") or 2)
        self.redis_socket_timeout_seconds = float(os.getenv("REDIS_SOCKET_TIMEOUT_SECONDS", "2") or 2)
        self.ttl_seconds = int(os.getenv("OTP_TTL_SECONDS", "120"))
        self.env = str(os.getenv("ENV", "development") or "development").strip().lower()
        self.is_production = self.env in {"prod", "production"}
        self.provider = str(provider or os.getenv("OTP_PROVIDER", "log") or "log").lower()
        if not self.is_production and not _allow_external_sms_in_dev() and self.provider != "log":
            logger.info("OTP provider %s disabled outside production; using log fallback.", self.provider)
            self.provider = "log"
        self.redis: Optional[Redis] = None
        self._memory_store: dict[str, tuple[str, float]] = {}
        self.sms_service = get_sms_service()
        self.hubtel_client = hubtel_client or HubtelOTPClient()

    async def _get_redis(self) -> Redis:
        if self.redis is None:
            self.redis = Redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=self.redis_connect_timeout_seconds,
                socket_timeout=self.redis_socket_timeout_seconds,
                retry_on_timeout=False,
            )
        return self.redis

    def _otp_key(self, identity: str, purpose: str = "register") -> str:
        return f"otp:{purpose}:{identity}"

    def _memory_set(self, key: str, otp_hash: str) -> None:
        self._memory_store[key] = (otp_hash, time.time() + self.ttl_seconds)

    def _memory_get(self, key: str) -> Optional[str]:
        payload = self._memory_store.get(key)
        if not payload:
            return None
        otp_hash, expires_at = payload
        if time.time() >= expires_at:
            self._memory_store.pop(key, None)
            return None
        return otp_hash

    def _memory_delete(self, key: str) -> None:
        self._memory_store.pop(key, None)

    def _serialize_session(self, session: dict) -> str:
        return json.dumps(session, separators=(",", ":"))

    def _deserialize_session(self, raw_value: str | None) -> Optional[dict]:
        if not raw_value:
            return None
        try:
            parsed = json.loads(raw_value)
        except Exception:
            return {"provider": "local", "otp_hash": raw_value}
        if isinstance(parsed, dict):
            return parsed
        return {"provider": "local", "otp_hash": raw_value}

    async def _save_session(self, key: str, session: dict) -> None:
        serialized = self._serialize_session(session)
        try:
            redis = await self._get_redis()
            await redis.set(key, serialized, ex=self.ttl_seconds)
            return
        except RedisConnectionError:
            log_fn = logger.warning if self.is_production else logger.info
            log_fn("Redis unavailable for OTP session save; using in-memory fallback for %s", key)
        except Exception as exc:
            log_fn = logger.warning if self.is_production else logger.info
            log_fn("OTP session save fallback for %s after redis error: %s", key, exc)
        self._memory_store[key] = (serialized, time.time() + self.ttl_seconds)

    async def _load_session(self, key: str) -> Optional[dict]:
        raw_value: Optional[str] = None
        try:
            redis = await self._get_redis()
            raw_value = await redis.get(key)
        except RedisConnectionError:
            raw_value = self._memory_get(key)
            log_fn = logger.warning if self.is_production else logger.info
            log_fn("Redis unavailable for OTP session load; using in-memory fallback for %s", key)
        except Exception as exc:
            raw_value = self._memory_get(key)
            log_fn = logger.warning if self.is_production else logger.info
            log_fn("OTP session load fallback for %s after redis error: %s", key, exc)
        return self._deserialize_session(raw_value)

    async def _delete_session(self, key: str) -> None:
        try:
            redis = await self._get_redis()
            await redis.delete(key)
        except Exception:
            pass
        self._memory_delete(key)

    async def issue_otp(
        self,
        identity: str,
        purpose: str = "register",
        recipient_email: str | None = None,
    ) -> tuple[str | None, dict]:
        key = self._otp_key(identity, purpose=purpose)
        hubtel_provider = self.provider in {"hubtel", "hubtel_otp"}

        if hubtel_provider:
            send_result = self.hubtel_client.send_otp(identity)
            if isinstance(send_result, dict) and str(send_result.get("status", "") or "").strip().lower() == "error":
                return None, send_result

            session = {
                "provider": "hubtel",
                "identity": str(identity or "").strip(),
                "purpose": str(purpose or "register").strip() or "register",
                "request_id": str(send_result.get("request_id", "") or "").strip(),
                "prefix": str(send_result.get("prefix", "") or "").strip(),
                "created_at": time.time(),
            }
            await self._save_session(key, session)
            return None, send_result

        otp_code = generate_otp()
        otp_hash = hash_password(otp_code)
        session = {
            "provider": "local",
            "otp_hash": otp_hash,
            "identity": str(identity or "").strip(),
            "purpose": str(purpose or "register").strip() or "register",
            "created_at": time.time(),
        }
        await self._save_session(key, session)

        message = f"Your CYBER CASH OTP is {otp_code}. It expires in 2 minutes."
        send_result = self.send_message(
            identity,
            message,
            sms_type="otp",
        )
        if isinstance(send_result, dict) and str(send_result.get("status", "") or "").strip().lower() == "error":
            await self._delete_session(key)

        return otp_code, send_result

    async def resend_otp(
        self,
        identity: str,
        purpose: str = "register",
        recipient_email: str | None = None,
    ) -> tuple[str | None, dict]:
        key = self._otp_key(identity, purpose=purpose)
        hubtel_provider = self.provider in {"hubtel", "hubtel_otp"}

        if hubtel_provider:
            session = await self._load_session(key)
            request_id = str((session or {}).get("request_id", "") or "").strip()
            if request_id:
                resend_result = self.hubtel_client.resend_otp(request_id)
                if isinstance(resend_result, dict) and str(resend_result.get("status", "") or "").strip().lower() == "error":
                    error_code = str(resend_result.get("code", "") or "").strip()
                    error_detail = str(resend_result.get("detail", "") or "").strip().lower()
                    if error_code == "2001" or "expired" in error_detail:
                        await self._delete_session(key)
                        return await self.issue_otp(identity, purpose=purpose, recipient_email=recipient_email)
                    return None, resend_result

                refreshed_prefix = str(resend_result.get("prefix", "") or "").strip() or str((session or {}).get("prefix", "") or "").strip()
                refreshed_request_id = str(resend_result.get("request_id", "") or "").strip() or request_id
                updated_session = {
                    **(session or {}),
                    "provider": "hubtel",
                    "identity": str(identity or "").strip(),
                    "purpose": str(purpose or "register").strip() or "register",
                    "request_id": refreshed_request_id,
                    "prefix": refreshed_prefix,
                    "created_at": time.time(),
                }
                await self._save_session(key, updated_session)
                return None, resend_result

        return await self.issue_otp(identity, purpose=purpose, recipient_email=recipient_email)

    async def verify_otp(self, identity: str, otp_code: str, purpose: str = "register") -> bool:
        key = self._otp_key(identity, purpose=purpose)
        session = await self._load_session(key)
        if not session:
            return False

        provider = str(session.get("provider", "local") or "local").strip().lower()
        if provider in {"hubtel", "hubtel_otp"}:
            request_id = str(session.get("request_id", "") or "").strip()
            prefix = str(session.get("prefix", "") or "").strip()
            if not request_id or not prefix:
                return False
            verification_result = self.hubtel_client.verify_otp(request_id, prefix, otp_code)
            valid = str(verification_result.get("status", "") or "").strip().lower() == "verified"
            if valid:
                await self._delete_session(key)
            return valid

        stored_hash = str(session.get("otp_hash", "") or "").strip()
        if not stored_hash:
            return False

        valid = verify_password(otp_code, stored_hash)
        if valid:
            await self._delete_session(key)
        return valid

    def send_sms(self, phone_number: str, message: str) -> dict:
        return self.send_message(phone_number, message)

    def send_message(self, phone_number: str, message: str, sms_type: str | None = None) -> dict:
        formatted_phone = self.sms_service.format_recipient(phone_number, provider=self.provider)
        if not formatted_phone:
            logger.warning("OTP SMS skipped due to invalid phone number: %s", phone_number)
            return {"status": "error", "provider": self.provider, "detail": "Invalid phone number"}
        if self.provider in {"mnotify", "hubtel", "arkesel", "twilio"}:
            return self.sms_service.send_sms(
                formatted_phone,
                message,
                sms_type=sms_type,
                provider=self.provider,
                sender_id=self.sms_service.sender_id,
            )

        # Safe default for local/dev/test.
        if sms_type == "otp":
            logger.info("OTP SMS (log, sender=%s) to %s", self.sms_service.sender_id, formatted_phone)
        else:
            logger.info("SMS (log, sender=%s) to %s: %s", self.sms_service.sender_id, formatted_phone, message)
        return {"status": "queued", "provider": self.provider, "recipient": formatted_phone, "sender_id": self.sms_service.sender_id}

    def _send_hubtel(self, phone_number: str, message: str) -> dict:
        client_id = os.getenv("HUBTEL_CLIENT_ID", "")
        client_secret = os.getenv("HUBTEL_CLIENT_SECRET", "")
        sender = os.getenv("HUBTEL_SENDER_ID", "CyberCash")
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
                return {"status": "queued", "provider": "hubtel", "recipient": phone_number, "http_status": response.status_code}
            return {
                "status": "error",
                "provider": "hubtel",
                "recipient": phone_number,
                "http_status": response.status_code,
                "detail": (response.text or "")[:300],
            }
        except Exception as exc:
            logger.warning("Hubtel SMS send failed: %s", exc)
            return {"status": "error", "provider": "hubtel", "recipient": phone_number, "detail": str(exc)}

    def _send_arkesel(self, phone_number: str, message: str) -> dict:
        api_key = os.getenv("ARKESEL_API_KEY", "")
        sender = os.getenv("ARKESEL_SENDER_ID", "CyberCash")
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
                return {"status": "queued", "provider": "arkesel", "recipient": phone_number, "http_status": response.status_code}
            return {
                "status": "error",
                "provider": "arkesel",
                "recipient": phone_number,
                "http_status": response.status_code,
                "detail": (response.text or "")[:300],
            }
        except Exception as exc:
            logger.warning("Arkesel SMS send failed: %s", exc)
            return {"status": "error", "provider": "arkesel", "recipient": phone_number, "detail": str(exc)}

    def _send_twilio(self, phone_number: str, message: str) -> dict:
        from twilio.rest import Client

        account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        from_number = os.getenv("TWILIO_FROM_NUMBER", "")
        try:
            client = Client(account_sid, auth_token)
            client.messages.create(
                body=message,
                from_=from_number,
                to=phone_number,
            )
            return {"status": "queued", "provider": "twilio", "recipient": phone_number}
        except Exception as exc:
            logger.warning("Twilio SMS send failed: %s", exc)
            return {"status": "error", "provider": "twilio", "recipient": phone_number, "detail": str(exc)}


_otp_service = OTPService()


def get_otp_service() -> OTPService:
    return _otp_service
