from email.utils import parseaddr

import pytest

from backend.core import mailer


def test_gmail_app_password_removes_display_grouping_spaces(monkeypatch):
    monkeypatch.setattr(mailer.settings, "MAIL_USERNAME", "sender@gmail.com")
    monkeypatch.setattr(mailer.settings, "MAIL_PASSWORD", "abcd efgh ijkl mnop")
    monkeypatch.setattr(mailer.settings, "MAIL_FROM", "sender@gmail.com")
    monkeypatch.setattr(mailer.settings, "MAIL_SERVER", "smtp.gmail.com")
    monkeypatch.setattr(mailer.settings, "MAIL_PORT", 587)
    monkeypatch.setattr(mailer.settings, "MAIL_FROM_NAME", "CyberCash")
    monkeypatch.setattr(mailer.settings, "MAIL_TIMEOUT_SECONDS", 15)

    config = mailer._connection_config()

    assert config.MAIL_PASSWORD.get_secret_value() == "abcdefghijklmnop"


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
    monkeypatch.setattr(mailer.settings, "MAIL_TIMEOUT_SECONDS", 15)

    config = mailer._connection_config()
    assert config.TIMEOUT == 15

    result = await mailer.send_email(
        "Account notice",
        [" Person@example.com ", "person@example.com", "other@example.com"],
        "Notice body",
    )

    assert result["status"] == "queued"
    assert "recipients" not in result
    assert len(sent) == 1
    assert [parseaddr(str(address))[1] for address in sent[0].recipients] == [
        "person@example.com",
        "other@example.com",
    ]


@pytest.mark.asyncio
async def test_send_email_uses_resend_http_api_when_configured(monkeypatch):
    captured = {}

    class FakeResponse:
        is_success = True
        status_code = 200

    class FakeClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, *, json, headers):
            captured.update(url=url, payload=json, headers=headers)
            return FakeResponse()

    monkeypatch.setattr(mailer.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(mailer.settings, "RESEND_API_KEY", "resend-test-key")
    monkeypatch.setattr(mailer.settings, "MAIL_PROVIDER", "resend")
    monkeypatch.setattr(mailer.settings, "MAIL_FROM", "noreply@example.com")
    monkeypatch.setattr(mailer.settings, "MAIL_FROM_NAME", "CyberCash")
    monkeypatch.setattr(mailer.settings, "MAIL_TIMEOUT_SECONDS", 15)

    result = await mailer.send_email("Verification", ["person@example.com"], "<p>Code</p>")

    assert result == {"status": "queued", "provider": "resend"}
    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["payload"] == {
        "from": "CyberCash <noreply@example.com>",
        "to": ["person@example.com"],
        "subject": "Verification",
        "html": "<p>Code</p>",
    }
    assert captured["headers"]["Authorization"] == "Bearer resend-test-key"
    assert captured["headers"]["Idempotency-Key"]


@pytest.mark.asyncio
async def test_resend_retry_reuses_idempotency_key(monkeypatch):
    requests = []
    responses = [type("Response", (), {"is_success": False, "status_code": 503})(),
                 type("Response", (), {"is_success": True, "status_code": 200})()]

    class FakeClient:
        def __init__(self, timeout):
            assert timeout.connect == 5

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, *, json, headers):
            requests.append(headers["Idempotency-Key"])
            return responses.pop(0)

    async def no_wait(_seconds):
        return None

    monkeypatch.setattr(mailer.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(mailer.asyncio, "sleep", no_wait)
    monkeypatch.setattr(mailer.settings, "RESEND_API_KEY", "resend-test-key")
    monkeypatch.setattr(mailer.settings, "MAIL_FROM", "noreply@example.com")
    monkeypatch.setattr(mailer.settings, "MAIL_PROVIDER", "resend")
    monkeypatch.setattr(mailer.settings, "MAIL_TIMEOUT_SECONDS", 15)

    result = await mailer.send_email("Verification", ["person@example.com"], "<p>Code</p>")

    assert result == {"status": "queued", "provider": "resend"}
    assert len(requests) == 2
    assert requests[0] == requests[1]


@pytest.mark.asyncio
async def test_selected_resend_provider_fails_fast_when_api_key_is_missing(monkeypatch):
    def smtp_must_not_run(*args, **kwargs):
        raise AssertionError("SMTP should not be used when Resend is selected")

    monkeypatch.setattr(mailer, "FastMail", smtp_must_not_run)
    monkeypatch.setattr(mailer.settings, "MAIL_PROVIDER", "resend")
    monkeypatch.setattr(mailer.settings, "RESEND_API_KEY", "")
    monkeypatch.setattr(mailer.settings, "MAIL_FROM", "noreply@example.com")

    result = await mailer.send_email("Verification", ["person@example.com"], "<p>Code</p>")

    assert result == {
        "status": "error",
        "provider": "email",
        "detail": "Email is temporarily unavailable. Please try again shortly.",
    }


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
        "detail": "Email is temporarily unavailable. Please try again shortly.",
    }


@pytest.mark.asyncio
async def test_send_email_does_not_log_transport_exception_details(monkeypatch, caplog):
    class FailingFastMail:
        def __init__(self, config):
            pass

        async def send_message(self, message):
            raise RuntimeError("recipient=owner@example.com password=mail-secret otp=123456")

    monkeypatch.setattr(mailer, "FastMail", FailingFastMail)
    monkeypatch.setattr(mailer.settings, "MAIL_USERNAME", "sender@example.com")
    monkeypatch.setattr(mailer.settings, "MAIL_PASSWORD", "secret")
    monkeypatch.setattr(mailer.settings, "MAIL_FROM", "sender@example.com")
    monkeypatch.setattr(mailer.settings, "MAIL_SERVER", "smtp.example.test")
    monkeypatch.setattr(mailer.settings, "MAIL_TIMEOUT_SECONDS", 15)

    config = mailer._connection_config()
    assert config.TIMEOUT == 15

    result = await mailer.send_email("Verification", ["owner@example.com"], "Code sent by email")

    assert result == {
        "status": "error",
        "provider": "email",
        "detail": "Email is temporarily unavailable. Please try again shortly.",
    }
    assert "owner@example.com" not in caplog.text
    assert "mail-secret" not in caplog.text
    assert "123456" not in caplog.text


@pytest.mark.asyncio
async def test_resend_stable_notification_key_deduplicates_repeated_sends(monkeypatch):
    keys = []

    class FakeResponse:
        is_success = True
        status_code = 200

    class FakeClient:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, *, json, headers):
            keys.append(headers["Idempotency-Key"])
            return FakeResponse()

    monkeypatch.setattr(mailer.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(mailer.settings, "RESEND_API_KEY", "resend-test-key")
    monkeypatch.setattr(mailer.settings, "MAIL_PROVIDER", "resend")
    monkeypatch.setattr(mailer.settings, "MAIL_FROM", "noreply@example.com")
    monkeypatch.setattr(mailer.settings, "MAIL_TIMEOUT_SECONDS", 15)

    for _ in range(2):
        result = await mailer.send_email(
            "Transaction update",
            ["person@example.com"],
            "Your transfer was completed.",
            idempotency_key="transaction:42:user:7:success",
        )
        assert result["status"] == "queued"

    assert len(keys) == 2
    assert keys[0] == keys[1]
    assert "transaction:42" not in keys[0]
    assert len(keys[0]) == 64
