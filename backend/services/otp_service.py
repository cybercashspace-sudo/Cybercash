import asyncio
import json
import logging
import os
import re
import secrets
import time
from typing import Optional

from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from backend.core.mailer import send_email
from backend.core.security import hash_password, verify_password
from backend.services.hubtel_otp import HubtelOTPClient

logger = logging.getLogger(__name__)


def generate_otp():
    return str(secrets.randbelow(900000) + 100000)


def _purpose_label(purpose: str) -> str:
    labels = {
        "access_verify": "account verification",
        "change_email": "email change",
        "register": "account registration",
        "reset_pin": "PIN reset",
    }
    normalized = str(purpose or "").strip().lower()
    return labels.get(normalized, "verification")


def _build_otp_email_body(otp_code: str, purpose: str) -> str:
    label = _purpose_label(purpose)
    return (
        "<div style='font-family: Arial, sans-serif; color: #1f2937; line-height: 1.6;'>"
        "<p>Hello,</p>"
        f"<p>Your CYBER CASH {label} code is <strong>{otp_code}</strong>.</p>"
        "<p>Enter this code in the app within 2 minutes to continue.</p>"
        "<p>Never share this code with anyone, including Cyber Cash staff. If you did not request it, you can ignore this email.</p>"
        "</div>"
    )


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
        self.provider = "email"
        self.redis: Optional[Redis] = None
        self._memory_store: dict[str, tuple[str, float]] = {}
        # Bounded lock stripes prevent parallel requests from issuing competing
        # codes for the same account in this single-worker production service.
        self._issue_locks = tuple(asyncio.Lock() for _ in range(64))
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
            log_fn("Redis unavailable for OTP session save; using in-memory fallback.")
        except Exception as exc:
            log_fn = logger.warning if self.is_production else logger.info
            log_fn("OTP session save fallback after Redis error (error_type=%s).", type(exc).__name__)
        self._memory_store[key] = (serialized, time.time() + self.ttl_seconds)

    async def _load_session(self, key: str) -> Optional[dict]:
        raw_value: Optional[str] = None
        try:
            redis = await self._get_redis()
            raw_value = await redis.get(key)
        except RedisConnectionError:
            raw_value = self._memory_get(key)
            log_fn = logger.warning if self.is_production else logger.info
            log_fn("Redis unavailable for OTP session load; using in-memory fallback.")
        except Exception as exc:
            raw_value = self._memory_get(key)
            log_fn = logger.warning if self.is_production else logger.info
            log_fn("OTP session load fallback after Redis error (error_type=%s).", type(exc).__name__)
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
        allow_refresh: bool = False,
    ) -> tuple[str | None, dict]:
        key = self._otp_key(identity, purpose=purpose)
        lock = self._issue_locks[hash(key) % len(self._issue_locks)]
        async with lock:
            return await self._issue_otp_locked(
                key,
                identity,
                purpose,
                recipient_email,
                allow_refresh,
            )

    async def _issue_otp_locked(
        self,
        key: str,
        identity: str,
        purpose: str,
        recipient_email: str | None,
        allow_refresh: bool,
    ) -> tuple[str | None, dict]:
        email = str(recipient_email or "").strip().lower()
        if not _is_valid_email(email):
            return None, {
                "status": "error",
                "provider": "email",
                "detail": "A valid account email is required to send an OTP.",
            }

        existing_session = await self._load_session(key)
        if existing_session:
            existing_email = str(existing_session.get("recipient_email", "") or "").strip().lower()
            if existing_email == email and not allow_refresh:
                return None, {
                    "status": "already_sent",
                    "provider": "email",
                    "detail": "A verification code is already active. Please check your inbox.",
                }
            if existing_email == email and allow_refresh:
                cooldown = max(15, int(os.getenv("OTP_RESEND_COOLDOWN_SECONDS", "30")))
                elapsed = time.time() - float(existing_session.get("created_at", 0) or 0)
                if elapsed < cooldown:
                    return None, {
                        "status": "already_sent",
                        "provider": "email",
                        "detail": "A code was sent recently. Please check your inbox or wait a few seconds before requesting another.",
                    }

        otp_code = generate_otp()
        otp_hash = hash_password(otp_code)
        session = {
            "provider": "local",
            "otp_hash": otp_hash,
            "identity": str(identity or "").strip(),
            "recipient_email": email,
            "purpose": str(purpose or "register").strip() or "register",
            "created_at": time.time(),
        }
        await self._save_session(key, session)

        send_result = await send_email(
            "Your CYBER CASH verification code",
            [email],
            _build_otp_email_body(otp_code, purpose),
        )
        if not isinstance(send_result, dict) or str(send_result.get("status", "") or "").strip().lower() != "queued":
            await self._delete_session(key)
            if not isinstance(send_result, dict):
                send_result = {"status": "error", "provider": "email", "detail": "Email delivery failed."}
            return None, send_result

        return otp_code, send_result

    async def resend_otp(
        self,
        identity: str,
        purpose: str = "register",
        recipient_email: str | None = None,
    ) -> tuple[str | None, dict]:
        return await self.issue_otp(identity, purpose=purpose, recipient_email=recipient_email, allow_refresh=True)

    async def verify_otp(
        self,
        identity: str,
        otp_code: str,
        purpose: str = "register",
        recipient_email: str | None = None,
    ) -> bool:
        key = self._otp_key(identity, purpose=purpose)
        session = await self._load_session(key)
        if not session:
            return False

        if recipient_email:
            expected_email = str(session.get("recipient_email", "") or "").strip().lower()
            if expected_email and expected_email != str(recipient_email).strip().lower():
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

_otp_service = OTPService()


def get_otp_service() -> OTPService:
    return _otp_service
