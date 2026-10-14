from __future__ import annotations

import time

import pytest

from backend.services import otp_service as otp_module
from backend.services.otp_service import OTPService


@pytest.mark.asyncio
async def test_otp_service_emails_new_and_resent_codes_once(monkeypatch):
    sent = []
    sessions = {}

    async def fake_send_email(subject, recipients, body):
        sent.append((subject, recipients, body))
        return {"status": "queued", "provider": "email", "recipients": recipients}

    async def save_session(key, value):
        sessions[key] = value

    async def load_session(key):
        return sessions.get(key)

    async def delete_session(key):
        sessions.pop(key, None)

    class NoSmsClient:
        def send_otp(self, *args):
            raise AssertionError("New OTPs must never use Hubtel/SMS")

        def resend_otp(self, *args):
            raise AssertionError("OTP resends must never use Hubtel/SMS")

    monkeypatch.setattr(otp_module, "send_email", fake_send_email)
    service = OTPService(provider="hubtel", hubtel_client=NoSmsClient())
    monkeypatch.setattr(service, "_save_session", save_session)
    monkeypatch.setattr(service, "_load_session", load_session)
    monkeypatch.setattr(service, "_delete_session", delete_session)

    otp_code, send_result = await service.issue_otp(
        "0247000101",
        purpose="access_verify",
        recipient_email=" Person@example.com ",
    )
    assert otp_code is not None
    assert send_result["provider"] == "email"
    assert len(sent) == 1
    assert sent[0][1] == ["person@example.com"]

    resent_code, resend_result = await service.resend_otp(
        "0247000101",
        purpose="access_verify",
        recipient_email="person@example.com",
    )
    assert resent_code is not None and resent_code != otp_code
    assert resend_result["provider"] == "email"
    assert len(sent) == 2
    assert await service.verify_otp("0247000101", resent_code, purpose="access_verify") is True


@pytest.mark.asyncio
async def test_legacy_hubtel_otp_sessions_remain_verifiable(monkeypatch):
    class FakeHubtelClient:
        def verify_otp(self, request_id: str, prefix: str, code: str) -> dict:
            assert (request_id, prefix, code) == ("REQ-1", "ABCD", "3824")
            return {"status": "verified", "provider": "hubtel"}

    service = OTPService(hubtel_client=FakeHubtelClient())
    session = {"provider": "hubtel", "request_id": "REQ-1", "prefix": "ABCD"}
    async def load_session(key):
        return session

    deleted = []
    async def delete_session(key):
        deleted.append(key)

    monkeypatch.setattr(service, "_load_session", load_session)
    monkeypatch.setattr(service, "_delete_session", delete_session)

    assert await service.verify_otp("0247000102", "3824", purpose="access_verify") is True
    assert deleted == [service._otp_key("0247000102", "access_verify")]


@pytest.mark.asyncio
async def test_failed_email_delivery_deletes_new_otp_session(monkeypatch):
    sessions = {}
    deleted = []

    async def failed_send_email(subject, recipients, body):
        return {"status": "error", "provider": "email", "detail": "SMTP unavailable"}

    async def save_session(key, value):
        sessions[key] = value

    async def delete_session(key):
        deleted.append(key)
        sessions.pop(key, None)

    monkeypatch.setattr(otp_module, "send_email", failed_send_email)
    service = OTPService()
    monkeypatch.setattr(service, "_save_session", save_session)
    monkeypatch.setattr(service, "_delete_session", delete_session)

    otp_code, result = await service.issue_otp(
        "0247000103",
        purpose="reset_pin",
        recipient_email="recover@example.com",
    )

    key = service._otp_key("0247000103", "reset_pin")
    assert otp_code is None
    assert result["status"] == "error"
    assert key in deleted
    assert key not in sessions
