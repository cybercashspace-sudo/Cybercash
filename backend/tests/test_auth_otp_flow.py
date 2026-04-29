from backend.models import User
from utils.security import hash_pin


def _register_payload(momo_number: str, pin: str = "1234", first_name: str = "Ama") -> dict:
    return {
        "momo_number": momo_number,
        "pin": pin,
        "is_agent": False,
        "first_name": first_name,
    }


def test_auth_otp_register_retry_and_reset_pin_flow(client, db_session):
    # New registration returns OTP and verify succeeds.
    verify_momo = "0247000001"
    register_response = client.post("/auth/register", json=_register_payload(verify_momo))
    assert register_response.status_code == 200
    register_payload = register_response.json()
    assert register_payload["status"] == "registered"
    assert register_payload["debug_otp"].isdigit()
    assert len(register_payload["debug_otp"]) == 6

    verify_response = client.post(
        "/auth/verify",
        json={"momo_number": verify_momo, "otp": register_payload["debug_otp"]},
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
    assert second_retry_payload["debug_otp"].isdigit()
    assert len(second_retry_payload["debug_otp"]) == 6

    # Reset-pin OTP accepts international number format and updated PIN can login.
    reset_local = "0247000003"
    reset_intl = "+233247000003"
    reset_register = client.post("/auth/register", json=_register_payload(reset_local, pin="1111"))
    assert reset_register.status_code == 200
    reset_register_payload = reset_register.json()

    reset_verify = client.post(
        "/auth/verify",
        json={"momo_number": reset_local, "otp": reset_register_payload["debug_otp"]},
    )
    assert reset_verify.status_code == 200

    request_reset_otp = client.post("/auth/reset-pin/request-otp", json={"momo_number": reset_intl})
    assert request_reset_otp.status_code == 200
    request_reset_payload = request_reset_otp.json()
    assert request_reset_payload["debug_otp"].isdigit()

    reset_pin_response = client.post(
        "/auth/reset-pin",
        json={
            "momo_number": reset_intl,
            "otp": request_reset_payload["debug_otp"],
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


def test_auth_access_returns_verify_required_for_unverified_user(client, db_session):
    momo_number = "0247000004"
    pin_hash = hash_pin("1234")
    db_session.add(
        User(
            momo_number=momo_number,
            phone_number=momo_number,
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
    assert access_payload["debug_otp"].isdigit()
    assert len(access_payload["debug_otp"]) == 6
