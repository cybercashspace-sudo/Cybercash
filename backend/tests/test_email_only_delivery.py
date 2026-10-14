import re

from backend.core.security import create_jwt
from backend.models import User, UserSettings
from backend.routes import auth as auth_routes
from backend.services import otp_service as otp_module
from utils.security import hash_pin
import pytest


def _new_user(db_session, *, momo_number: str, email: str | None) -> User:
    pin_hash = hash_pin("1234")
    user = User(
        momo_number=momo_number,
        phone_number=momo_number,
        email=email,
        full_name="Email Delivery User",
        pin_hash=pin_hash,
        password_hash=pin_hash,
        is_verified=False,
        role="user",
        status="active",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.mark.parametrize("purpose", ["register", "reset_pin"])
def test_existing_account_otp_ignores_caller_email_and_uses_saved_email(client, db_session, monkeypatch, purpose):
    user = _new_user(db_session, momo_number="0247000091", email="owner@example.com")
    sent = []

    async def fake_send_email(subject, recipients, body):
        sent.append((subject, recipients, body))
        return {"status": "queued", "provider": "email"}

    monkeypatch.setattr(otp_module, "send_email", fake_send_email)
    response = client.post(
        "/otp/send",
        json={
            "momo_number": user.momo_number,
            "purpose": purpose,
            "email": "attacker@example.com",
        },
    )

    assert response.status_code == 200
    assert len(sent) == 1
    assert sent[0][1] == ["owner@example.com"]


def test_existing_account_without_saved_email_cannot_request_otp(client, db_session, monkeypatch):
    user = _new_user(db_session, momo_number="0247000092", email=None)
    sent = []

    async def fake_send_email(*args):
        sent.append(args)
        return {"status": "queued", "provider": "email"}

    monkeypatch.setattr(otp_module, "send_email", fake_send_email)
    response = client.post(
        "/otp/send",
        json={
            "momo_number": user.momo_number,
            "purpose": "reset_pin",
            "email": "attacker@example.com",
        },
    )

    assert response.status_code == 409
    assert sent == []


def test_registration_never_returns_otp_code_outside_test_mode(client, monkeypatch):
    async def fake_send_email(subject, recipients, body):
        assert recipients == ["production@example.com"]
        assert re.search(r"\d{6}", body)
        return {"status": "queued", "provider": "email"}

    monkeypatch.setattr(otp_module, "send_email", fake_send_email)
    monkeypatch.setenv("RUNNING_TESTS", "false")

    response = client.post(
        "/auth/register",
        json={
            "momo_number": "0247000098",
            "email": "production@example.com",
            "pin": "1234",
            "first_name": "Ama",
        },
    )

    assert response.status_code == 200
    assert "debug_otp" not in response.json()


def test_access_account_creation_requires_and_sends_email(client, db_session, monkeypatch):
    sent = []

    async def fake_send_email(subject, recipients, body):
        sent.append((recipients, body))
        return {"status": "queued", "provider": "email"}

    monkeypatch.setattr(otp_module, "send_email", fake_send_email)
    missing_email = client.post(
        "/auth/access",
        json={"momo_number": "0247000093", "pin": "1234", "first_name": "Ama"},
    )
    assert missing_email.status_code == 400
    assert sent == []

    response = client.post(
        "/auth/access",
        json={
            "momo_number": "0247000094",
            "pin": "1234",
            "first_name": "Ama",
            "email": "new-user@example.com",
        },
    )
    assert response.status_code == 200
    assert len(sent) == 1
    assert sent[0][0] == ["new-user@example.com"]
    user = db_session.query(User).filter(User.momo_number == "0247000094").one()
    assert user.email == "new-user@example.com"


def test_outbound_sms_endpoint_is_disabled(client, db_session):
    user = _new_user(db_session, momo_number="0247000095", email="sms-user@example.com")
    token = create_jwt(user.id, token_version=0)

    response = client.post(
        "/api/sms/send",
        headers={"Authorization": f"Bearer {token}"},
        json={"phone": user.momo_number, "message": "Do not send by SMS"},
    )

    assert response.status_code == 410
    assert response.json()["detail"] == "SMS notifications are disabled. Notifications are sent to account email only."


def test_user_notification_preferences_cannot_enable_sms(client, db_session):
    user = _new_user(db_session, momo_number="0247000097", email="prefs@example.com")
    token = create_jwt(user.id, token_version=0)
    headers = {"Authorization": f"Bearer {token}"}

    read_response = client.get("/settings/me", headers=headers)
    assert read_response.status_code == 200
    assert read_response.json()["sms_alerts"] is False
    assert read_response.json()["email_alerts"] is True

    update_response = client.put(
        "/settings/me",
        headers=headers,
        json={"sms_alerts": True, "email_alerts": False},
    )
    assert update_response.status_code == 200
    assert update_response.json()["sms_alerts"] is False
    assert update_response.json()["email_alerts"] is True

    settings_row = db_session.query(UserSettings).filter(UserSettings.user_id == user.id).one()
    assert settings_row.sms_alerts is False
    assert settings_row.email_alerts is True


def test_authenticated_email_change_requires_code_sent_to_requested_address(client, db_session, monkeypatch):
    user = _new_user(db_session, momo_number="0247000096", email=None)
    token = create_jwt(user.id, token_version=0)
    headers = {"Authorization": f"Bearer {token}"}
    sent = []

    async def fake_send_email(subject, recipients, body):
        sent.append((subject, recipients, body))
        return {"status": "queued", "provider": "email"}

    monkeypatch.setattr(otp_module, "send_email", fake_send_email)
    monkeypatch.setattr(auth_routes, "send_email", fake_send_email)
    request_response = client.post(
        "/auth/email/change/request",
        headers=headers,
        json={"email": "verified@example.com"},
    )
    assert request_response.status_code == 200
    assert len(sent) == 1
    assert sent[0][1] == ["verified@example.com"]
    otp_match = re.search(r"<strong>(\d{6})</strong>", sent[0][2])
    assert otp_match
    otp = otp_match.group(1)

    wrong_address = client.post(
        "/auth/email/change/verify",
        headers=headers,
        json={"email": "other@example.com", "otp": otp},
    )
    assert wrong_address.status_code == 400

    verify_response = client.post(
        "/auth/email/change/verify",
        headers=headers,
        json={"email": "verified@example.com", "otp": otp},
    )
    assert verify_response.status_code == 200
    db_session.expire_all()
    assert db_session.query(User).filter(User.id == user.id).one().email == "verified@example.com"
    assert len(sent) == 2


def test_email_change_rate_limit_is_per_account_not_per_destination(client, db_session, monkeypatch):
    user = _new_user(db_session, momo_number="0247000099", email=None)
    token = create_jwt(user.id, token_version=0)
    headers = {"Authorization": f"Bearer {token}"}
    sent = []
    monkeypatch.setattr(auth_routes, "_RATE_LIMIT_STATE", {})

    async def fake_send_email(subject, recipients, body):
        sent.append(recipients)
        return {"status": "queued", "provider": "email"}

    monkeypatch.setattr(otp_module, "send_email", fake_send_email)
    responses = [
        client.post(
            "/auth/email/change/request",
            headers=headers,
            json={"email": f"address{index}@example.com"},
        )
        for index in range(6)
    ]

    assert any(response.status_code == 429 for response in responses)
    assert len(sent) < len(responses)