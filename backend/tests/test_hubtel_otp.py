from __future__ import annotations

import pytest

from backend.services.hubtel_otp import HubtelOTPClient
from backend.services.otp_service import OTPService


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> dict:
        return self._payload


def test_hubtel_client_formats_send_resend_and_verify_requests(monkeypatch):
    monkeypatch.setenv("HUBTEL_AUTH", "Basic test-token")
    monkeypatch.setenv("HUBTEL_BASE_URL", "https://api-otp.hubtel.com")
    monkeypatch.setenv("HUBTEL_SENDER_ID", "CyberCash")
    monkeypatch.setenv("HUBTEL_COUNTRY_CODE", "GH")

    calls: list[dict] = []

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append(
            {
                "url": url,
                "json": json,
                "headers": headers,
                "timeout": timeout,
            }
        )
        if url.endswith("/otp/send"):
            return _FakeResponse(
                200,
                {
                    "message": "success",
                    "code": "0000",
                    "data": {"requestId": "REQ-1", "prefix": "ABCD"},
                },
            )
        if url.endswith("/otp/resend"):
            return _FakeResponse(
                200,
                {
                    "message": "success",
                    "code": "0000",
                    "data": {"requestId": "REQ-1", "prefix": "WXYZ"},
                },
            )
        if url.endswith("/otp/verify"):
            return _FakeResponse(200, text="")
        return _FakeResponse(500, {"message": "unknown"})

    monkeypatch.setattr("backend.services.hubtel_otp.requests.post", fake_post, raising=True)

    client = HubtelOTPClient()

    send_result = client.send_otp("0241234567")
    assert send_result["status"] == "queued"
    assert send_result["request_id"] == "REQ-1"
    assert send_result["prefix"] == "ABCD"
    assert calls[0]["json"]["phoneNumber"] == "+233241234567"
    assert calls[0]["headers"]["Authorization"] == "Basic test-token"

    resend_result = client.resend_otp("REQ-1")
    assert resend_result["status"] == "queued"
    assert resend_result["prefix"] == "WXYZ"

    verify_result = client.verify_otp("REQ-1", "WXYZ", "3824")
    assert verify_result["status"] == "verified"
    assert calls[-1]["url"].endswith("/otp/verify")
    assert calls[-1]["json"]["code"] == "3824"


@pytest.mark.asyncio
async def test_otp_service_uses_hubtel_sessions(monkeypatch):
    monkeypatch.setenv("ALLOW_EXTERNAL_SMS_IN_DEV", "1")

    class FakeHubtelClient:
        def __init__(self):
            self.sent = []
            self.resends = []
            self.verifies = []

        def send_otp(self, phone_number: str) -> dict:
            self.sent.append(phone_number)
            return {
                "status": "queued",
                "provider": "hubtel",
                "request_id": "REQ-1",
                "prefix": "ABCD",
            }

        def resend_otp(self, request_id: str) -> dict:
            self.resends.append(request_id)
            return {
                "status": "queued",
                "provider": "hubtel",
                "request_id": request_id,
                "prefix": "WXYZ",
            }

        def verify_otp(self, request_id: str, prefix: str, code: str) -> dict:
            self.verifies.append((request_id, prefix, code))
            return {"status": "verified", "provider": "hubtel"}

    fake_client = FakeHubtelClient()
    service = OTPService(provider="hubtel", hubtel_client=fake_client)

    otp_code, send_result = await service.issue_otp("0247000101", purpose="access_verify")
    assert otp_code is None
    assert send_result["request_id"] == "REQ-1"
    assert fake_client.sent == ["0247000101"]

    resend_code, resend_result = await service.resend_otp("0247000101", purpose="access_verify")
    assert resend_code is None
    assert resend_result["prefix"] == "WXYZ"
    assert fake_client.resends == ["REQ-1"]

    verified = await service.verify_otp("0247000101", "3824", purpose="access_verify")
    assert verified is True
    assert fake_client.verifies == [("REQ-1", "WXYZ", "3824")]
