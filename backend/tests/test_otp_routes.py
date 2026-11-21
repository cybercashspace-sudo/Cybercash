import pytest

from backend.services import otp_service


def test_otp_generation_uses_secure_random_source(monkeypatch):
    calls = []

    def secure_value(limit):
        calls.append(limit)
        return limit - 1

    monkeypatch.setattr(otp_service.secrets, "randbelow", secure_value)

    assert otp_service.generate_otp() == "999999"
    assert calls == [900000]


@pytest.mark.asyncio
async def test_otp_storage_fallback_does_not_log_phone_or_email(monkeypatch, caplog):
    class OfflineRedis:
        async def get(self, key):
            raise otp_service.RedisConnectionError("redis://private-host/session")

        async def set(self, key, value, ex):
            raise otp_service.RedisConnectionError("redis://private-host/session")

    async def queue_email(subject, recipients, body):
        return {"status": "queued", "provider": "email"}

    monkeypatch.setattr(otp_service, "send_email", queue_email)
    service = otp_service.OTPService()
    service.redis = OfflineRedis()

    await service.issue_otp(
        "0247000999",
        purpose="access_verify",
        recipient_email="private@example.com",
        allow_refresh=True,
    )

    assert "0247000999" not in caplog.text
    assert "private@example.com" not in caplog.text
    assert "private-host" not in caplog.text


def test_otp_routes_support_send_verify_and_resend(client, monkeypatch):
    phone_number = "0247000100"
    emailed_codes = []

    async def capture_email(subject, recipients, body):
        import re

        match = re.search(r"<strong>(\d{6})</strong>", body)
        if match:
            emailed_codes.append(match.group(1))
        return {"status": "queued", "provider": "email"}

    monkeypatch.setattr(otp_service, "send_email", capture_email)

    send_response = client.post(
        "/otp/send",
        json={"momo_number": phone_number, "purpose": "register", "email": "new@example.com"},
    )
    assert send_response.status_code == 200
    send_payload = send_response.json()
    assert send_payload["message"] == "OTP sent to the email saved on your account."
    assert "debug_otp" not in send_payload
    assert emailed_codes[-1].isdigit()
    assert len(emailed_codes[-1]) == 6

    verify_response = client.post(
        "/otp/verify",
        json={"momo_number": phone_number, "otp": emailed_codes[-1], "purpose": "register"},
    )
    assert verify_response.status_code == 200
    assert verify_response.json()["message"] == "OTP verified"

    resend_response = client.post(
        "/otp/resend",
        json={"momo_number": phone_number, "purpose": "register", "email": "new@example.com"},
    )
    assert resend_response.status_code == 200
    resend_payload = resend_response.json()
    assert resend_payload["message"] == "A new OTP was sent to the email saved on your account."
    assert "debug_otp" not in resend_payload
    assert emailed_codes[-1].isdigit()
    assert len(emailed_codes[-1]) == 6
