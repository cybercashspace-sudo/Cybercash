from types import SimpleNamespace

import pytest

from backend.services import notification


@pytest.mark.asyncio
async def test_send_to_users_sends_once_per_unique_email(monkeypatch):
    sends = []

    async def fake_send_email(subject, recipients, body):
        sends.append((subject, recipients, body))
        return {"status": "queued", "provider": "email"}

    monkeypatch.setattr(notification, "send_email", fake_send_email)
    users = [
        SimpleNamespace(id=1, email="Person@example.com"),
        SimpleNamespace(id=2, email=" person@example.com "),
        SimpleNamespace(id=3, email="other@example.com"),
    ]

    result = await notification.NotificationService().send_to_users(users, "Notice")

    assert result == {
        "status": "queued",
        "provider": "email",
        "recipient_count": 2,
        "sent_count": 2,
        "failed_count": 0,
    }
    assert len(sends) == 2
    assert all(len(recipients) == 1 for _, recipients, _ in sends)
    assert {recipients[0] for _, recipients, _ in sends} == {
        "person@example.com",
        "other@example.com",
    }


@pytest.mark.asyncio
async def test_send_to_user_does_not_fallback_to_sms_without_email(monkeypatch):
    async def fail_if_called(*args, **kwargs):
        raise AssertionError("Email must not be attempted without a valid address")

    monkeypatch.setattr(notification, "send_email", fail_if_called)
    user = SimpleNamespace(id=4, email=None)

    result = await notification.NotificationService().send_to_user(user, "Notice")

    assert result["status"] == "error"
    assert result["provider"] == "email"
    assert "valid account email" in result["detail"]