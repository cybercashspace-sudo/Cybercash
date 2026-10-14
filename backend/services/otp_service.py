import json
import logging
import os
import random
import re
import time
from typing import Optional

from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from backend.core.mailer import send_email
from backend.core.security import hash_password, verify_password
from backend.services.hubtel_otp import HubtelOTPClient

logger = logging.getLogger(__name__)


def generate_otp():
    return str(random.randint(100000, 999999))


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
        email = str(recipient_email or "").strip().lower()
        if not _is_valid_email(email):
            return None, {
                "status": "error",
                "provider": "email",
                "detail": "A valid account email is required to send an OTP.",
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
            f"<p>Your CYBER CASH OTP is <strong>{otp_code}</strong>.</p><p>It expires in 2 minutes. Do not share it with anyone.</p>",
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
        return await self.issue_otp(identity, purpose=purpose, recipient_email=recipient_email)

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
