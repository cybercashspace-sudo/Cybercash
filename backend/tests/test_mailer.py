from email.utils import parseaddr

import pytest

from backend.core import mailer


@pytest.mark.asyncio
async def test_send_email_deduplicates_recipients(monkeypatch):
    sent = []

    class FakeFastMail:
        def __init__(self, config):
            pass

        async def send_message(self, message):
            sent.append(message)

    monkeypatch.setattr(mailer, "FastMail", FakeFastMail)
    monkeypatch.setattr(mailer.settings, "MAIL_USERNAME", "sender@example.com")
    monkeypatch.setattr(mailer.settings, "MAIL_PASSWORD", "secret")
    monkeypatch.setattr(mailer.settings, "MAIL_FROM", "sender@example.com")
    monkeypatch.setattr(mailer.settings, "MAIL_SERVER", "smtp.example.test")

    result = await mailer.send_email(
        "Account notice",
        [" Person@example.com ", "person@example.com", "other@example.com"],
        "Notice body",
    )

    assert result["status"] == "queued"
    assert len(sent) == 1
    assert [parseaddr(str(address))[1] for address in sent[0].recipients] == [
        "person@example.com",
        "other@example.com",
    ]


@pytest.mark.asyncio
async def test_send_email_fails_closed_when_smtp_is_unconfigured(monkeypatch):
    monkeypatch.setattr(mailer.settings, "MAIL_USERNAME", None)
    monkeypatch.setattr(mailer.settings, "MAIL_PASSWORD", None)
    monkeypatch.setattr(mailer.settings, "MAIL_FROM", None)
    monkeypatch.setattr(mailer.settings, "MAIL_SERVER", None)

    result = await mailer.send_email("OTP", ["person@example.com"], "Never log this OTP")

    assert result == {
        "status": "error",
        "provider": "email",
        "detail": "Email delivery is not configured.",
    }