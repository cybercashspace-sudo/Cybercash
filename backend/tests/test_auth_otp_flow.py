import re

from backend.models import Agent, User, Wallet
from backend.services import otp_service
from utils.security import hash_pin


def _register_payload(momo_number: str, pin: str = "1234", first_name: str = "Ama") -> dict:
    return {
        "momo_number": momo_number,
        "email": f"user{momo_number[-4:]}@example.com",
        "pin": pin,
        "is_agent": False,
        "first_name": first_name,
    }


def _capture_otp_emails(monkeypatch):
    codes = []

    async def capture_email(subject, recipients, body):
        match = re.search(r"<strong>(\d{6})</strong>", body)
        if match:
            codes.append(match.group(1))
        return {"status": "queued", "provider": "email"}

    monkeypatch.setattr(otp_service, "send_email", capture_email)
    return codes


def test_auth_otp_register_retry_and_reset_pin_flow(client, db_session, monkeypatch):
    emailed_codes = _capture_otp_emails(monkeypatch)
    # New registration returns OTP and verify succeeds.
    verify_momo = "0247000001"
    register_response = client.post("/auth/register", json=_register_payload(verify_momo))
    assert register_response.status_code == 200
    register_payload = register_response.json()
    assert register_payload["status"] == "registered"
    assert "debug_otp" not in register_payload
    assert emailed_codes[-1].isdigit()
    assert len(emailed_codes[-1]) == 6

    verify_response = client.post(
        "/auth/verify",
        json={"momo_number": verify_momo, "otp": emailed_codes[-1]},
    )
    assert verify_response.status_code == 200
    assert verify_response.json()["status"] == "verified"

    user = db_session.query(User).filter(User.momo_number == verify_momo).first()
    assert user is not None
    assert bool(user.is_verified) is True

    # Retry registration on an unverified profile returns verify_required + fresh OTP.
    retry_momo = "0247000002"
    first_retry = client.post("/auth/register", json=_register_payload(retry_momo))
    assert first_retry.status_code == 200
    assert first_retry.json()["status"] == "registered"

    second_retry = client.post("/auth/register", json=_register_payload(retry_momo))
    assert second_retry.status_code == 200
    second_retry_payload = second_retry.json()
    assert second_retry_payload["status"] == "verify_required"
    assert "debug_otp" not in second_retry_payload
    assert emailed_codes[-1].isdigit()
    assert len(emailed_codes[-1]) == 6

    # Reset-pin OTP accepts international number format and updated PIN can login.
    reset_local = "0247000003"
    reset_intl = "+233247000003"
    reset_register = client.post("/auth/register", json=_register_payload(reset_local, pin="1111"))
    assert reset_register.status_code == 200
    reset_register_payload = reset_register.json()

    reset_verify = client.post(
        "/auth/verify",
        json={"momo_number": reset_local, "otp": emailed_codes[-1]},
    )
    assert reset_verify.status_code == 200

    request_reset_otp = client.post("/auth/reset-pin/request-otp", json={"momo_number": reset_intl})
    assert request_reset_otp.status_code == 200
    request_reset_payload = request_reset_otp.json()
    assert "debug_otp" not in request_reset_payload
    assert emailed_codes[-1].isdigit()

    reset_pin_response = client.post(
        "/auth/reset-pin",
        json={
            "momo_number": reset_intl,
            "otp": emailed_codes[-1],
            "new_pin": "9999",
        },
    )
    assert reset_pin_response.status_code == 200

    access_response = client.post(
        "/auth/access",
        json={
            "momo_number": reset_local,
            "pin": "9999",
            "first_name": "Ama",
            "is_agent": False,
        },
    )
    assert access_response.status_code == 200
    assert access_response.json()["status"] == "login_success"


def test_auth_access_returns_verify_required_for_unverified_user(client, db_session, monkeypatch):
    emailed_codes = _capture_otp_emails(monkeypatch)
    momo_number = "0247000004"
    pin_hash = hash_pin("1234")
    db_session.add(
        User(
            momo_number=momo_number,
            phone_number=momo_number,
            email="existing@example.com",
            pin_hash=pin_hash,
            password_hash=pin_hash,
            full_name="Ama Test",
            provider="MTN",
            is_verified=False,
            is_agent=False,
            role="user",
            status="active",
        )
    )
    db_session.commit()

    access_response = client.post(
        "/auth/access",
        json={
            "momo_number": momo_number,
            "pin": "1234",
            "first_name": "Ama",
            "is_agent": False,
        },
    )
    assert access_response.status_code == 200
    access_payload = access_response.json()
    assert access_payload["status"] == "verify_required"
    assert "debug_otp" not in access_payload
    assert emailed_codes[-1].isdigit()
    assert len(emailed_codes[-1]) == 6


def test_pending_agent_can_sign_in_to_regular_user_account(client, db_session):
    pin_hash = hash_pin("1234")
    user = User(
        momo_number="0247000015",
        phone_number="0247000015",
        email="pending-agent@example.com",
        full_name="Ama Agent",
        pin_hash=pin_hash,
        password_hash=pin_hash,
        is_active=True,
        is_verified=True,
        is_agent=True,
        role="agent",
        status="pending_kyc",
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(Wallet(user_id=user.id, currency="GHS", balance=0.0))
    agent = Agent(user_id=user.id, status="pending_kyc", float_balance=0.0)
    db_session.add(agent)
    db_session.commit()

    response = client.post(
        "/auth/access",
        json={"momo_number": user.momo_number, "pin": "1234"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "login_success"
    assert payload["access_token"]

    profile = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {payload['access_token']}"},
    )
    assert profile.status_code == 200, profile.text
    assert profile.json()["is_agent"] is False
    assert profile.json()["role"] == "user"

    owner_update = client.put(
        f"/agents/{agent.id}",
        headers={"Authorization": f"Bearer {payload['access_token']}"},
        json={"status": "active"},
    )
    assert owner_update.status_code == 403

    sale = client.post(
        "/agents/me/sell-airtime",
        headers={"Authorization": f"Bearer {payload['access_token']}"},
        json={"phone_number": "0247000015", "amount": 1, "currency": "GHS", "network_provider": "MTN"},
    )
    assert sale.status_code == 403

    db_session.expire_all()
    stored_user = db_session.query(User).filter_by(id=user.id).one()
    assert stored_user.is_agent is True
