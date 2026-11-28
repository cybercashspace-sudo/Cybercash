import asyncio
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
async def test_send_to_users_delivers_concurrently_with_a_bounded_limit(monkeypatch):
    active_sends = 0
    maximum_active_sends = 0

    async def fake_send_email(subject, recipients, body):
        nonlocal active_sends, maximum_active_sends
        active_sends += 1
        maximum_active_sends = max(maximum_active_sends, active_sends)
        await asyncio.sleep(0.01)
        active_sends -= 1
        return {"status": "queued", "provider": "email"}

    monkeypatch.setattr(notification, "send_email", fake_send_email)
    users = [
        SimpleNamespace(id=index, email=f"person{index}@example.com")
        for index in range(12)
    ]

    result = await notification.NotificationService().send_to_users(users, "Notice")

    assert result["status"] == "queued"
    assert result["sent_count"] == len(users)
    assert maximum_active_sends == notification._EMAIL_NOTIFICATION_CONCURRENCY


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


@pytest.mark.asyncio
async def test_send_transaction_notification_sends_for_completed_transaction(monkeypatch):
    sends = []

    async def fake_send_email(subject, recipients, body):
        sends.append((subject, recipients, body))
        return {"status": "queued", "provider": "email"}

    monkeypatch.setattr(notification, "send_email", fake_send_email)
    user = SimpleNamespace(id=7, email="customer@example.com")

    result = await notification.NotificationService().send_transaction_notification(
        user,
        "deposit",
        250.0,
        currency="GHS",
        subject="Transaction update",
    )

    assert result["status"] == "queued"
    assert len(sends) == 1
    assert sends[0][0] == "Transaction update"
    assert "deposit" in sends[0][2].lower()
    assert "250" in sends[0][2]
    assert "ghs" in sends[0][2].lower()


@pytest.mark.asyncio
async def test_transfer_email_includes_both_party_names_and_numbers_safely(monkeypatch):
    sends = []

    async def fake_send_email(subject, recipients, body, **kwargs):
        sends.append((subject, recipients, body, kwargs))
        return {"status": "queued", "provider": "email"}

    monkeypatch.setattr(notification, "send_email", fake_send_email)
    user = SimpleNamespace(id=8, email="sender@example.com")

    result = await notification.NotificationService().send_transaction_notification(
        user,
        "transfer",
        25,
        direction="send",
        sender_name="Ama Mensah",
        sender_number="0241234567",
        receiver_name="Kojo <Test>",
        receiver_number="0207654321",
        idempotency_key="transaction:8:user:8:success",
    )

    assert result["status"] == "queued"
    assert len(sends) == 1
    body = sends[0][2]
    assert "Sender: Ama Mensah (0241234567)" in body
    assert "Receiver: Kojo &lt;Test&gt; (0207654321)" in body
    assert sends[0][3]["idempotency_key"] == "transaction:8:user:8:success"


@pytest.mark.parametrize(
    ("transaction_type", "expected_label"),
    [
        ("AGENT_WITHDRAWAL", "withdrawal"),
        ("LOAN_DISBURSE", "loan disbursement"),
        ("LOAN_REPAY", "loan repayment"),
        ("INVESTMENT_CREATE", "investment"),
        ("INVESTMENT_PAYOUT", "investment payout"),
        ("ESCROW_CREATE", "escrow funding"),
        ("ESCROW_RELEASE", "escrow release"),
        ("CARD_LOAD", "card top-up"),
        ("CARD_SPEND", "card purchase"),
        ("DATA", "data bundle purchase"),
        ("AIRTIME", "airtime purchase"),
    ],
)
def test_transaction_types_have_user_friendly_notification_labels(transaction_type, expected_label):
    assert notification._humanize_transaction_type(transaction_type) == expected_label
