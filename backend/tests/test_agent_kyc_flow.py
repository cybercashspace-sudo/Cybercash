import io
from unittest.mock import AsyncMock

from PIL import Image

from backend.core.security import create_access_token
from backend.models import Agent, AgentProfile, Transaction, User, Wallet
from backend.services.kyc_storage import decrypt_identity


def _jpeg_bytes(color):
    stream = io.BytesIO()
    Image.new("RGB", (48, 48), color).save(stream, format="JPEG")
    return stream.getvalue()


def _headers(email):
    return {"Authorization": f"Bearer {create_access_token(data={'sub': email})}"}


def _create_paid_agent(db_session, *, user_id=8821, email="kyc-owner@example.com"):
    user = User(
        id=user_id,
        email=email,
        full_name="KYC Applicant",
        password_hash="test-hash",
        is_active=True,
        is_verified=True,
        is_admin=False,
        is_agent=False,
        role="user",
    )
    db_session.add(user)
    db_session.flush()
    wallet = Wallet(user_id=user.id, currency="GHS", balance=0.0)
    db_session.add(wallet)
    db_session.flush()
    agent = Agent(user_id=user.id, status="pending_kyc", float_balance=0.0)
    db_session.add(agent)
    db_session.flush()
    db_session.add(
        Transaction(
            user_id=user.id,
            wallet_id=wallet.id,
            agent_id=agent.id,
            type="agent_registration_fee",
            entry_type="credit",
            amount=100.0,
            currency="GHS",
            status="completed",
            provider="paystack",
            provider_reference=f"kyc-test-{user_id}",
        )
    )
    db_session.commit()
    return user, agent


def test_agent_kyc_upload_is_encrypted_and_admin_only(client, db_session, monkeypatch):
    from backend.routes import agents as agent_routes

    user, agent = _create_paid_agent(db_session)
    mail = AsyncMock(return_value={"status": "queued", "provider": "email"})
    monkeypatch.setattr(agent_routes, "send_email", mail)
    files = {
        "ghana_card_front": ("front.jpg", _jpeg_bytes((20, 60, 110)), "image/jpeg"),
        "ghana_card_back": ("back.jpg", _jpeg_bytes((30, 70, 120)), "image/jpeg"),
        "selfie_with_id": ("selfie.jpg", _jpeg_bytes((40, 80, 130)), "image/jpeg"),
    }
    response = client.post(
        "/agents/me/kyc/submit",
        headers=_headers(user.email),
        data={
            "full_name": "KYC Applicant",
            "date_of_birth": "1990-01-02",
            "ghana_card_number": "GHA-123456789-0",
            "consent": "true",
        },
        files=files,
    )

    assert response.status_code == 200, response.text
    assert response.json()["kyc_status"] == "pending_admin_review"
    assert response.json()["notification_sent"] is True
    mail.assert_awaited_once()
    assert "123456789" not in mail.await_args.args[2]
    assert "data:image" not in mail.await_args.args[2]

    db_session.expire_all()
    profile = db_session.query(AgentProfile).filter_by(user_id=user.id).one()
    assert profile.ghana_card_number is None
    assert profile.identity_data_encrypted != "GHA-123456789-0"
    assert decrypt_identity(profile.identity_data_encrypted)["ghana_card_number"] == "GHA-123456789-0"
    assert profile.ghana_card_front_ref is None
    assert profile.ghana_card_front_encrypted
    updated_agent = db_session.query(Agent).filter_by(id=agent.id).one()
    assert updated_agent.status == "pending_kyc_review"

    assert client.get("/admin/agents/kyc-pending", headers=_headers(user.email)).status_code == 403


def test_admin_reviews_and_approves_only_a_complete_paid_kyc(client, db_session, admin_auth_headers):
    user, agent = _create_paid_agent(db_session, user_id=8822, email="kyc-approval@example.com")
    from backend.services.kyc_storage import encrypt_identity, encrypt_image, normalize_image

    photo, _mime = normalize_image(_jpeg_bytes((50, 90, 140)))
    profile = AgentProfile(
        user_id=user.id,
        kyc_status="pending_admin_review",
        identity_data_encrypted=encrypt_identity("KYC Applicant", "1990-01-02", "GHA-987654321-0"),
        ghana_card_front_encrypted=encrypt_image(photo),
        ghana_card_back_encrypted=encrypt_image(photo),
        selfie_encrypted=encrypt_image(photo),
    )
    db_session.add(profile)
    agent.status = "pending_kyc_review"
    db_session.commit()

    pending = client.get("/admin/agents/kyc-pending", headers=admin_auth_headers)
    assert pending.status_code == 200
    assert any(item["agent_id"] == agent.id for item in pending.json())

    details = client.get(f"/admin/agents/{agent.id}/kyc-review", headers=admin_auth_headers)
    assert details.status_code == 200
    assert details.json()["ghana_card_number"] == "GHA-987654321-0"
    assert details.json()["ghana_card_front"].startswith("data:image/jpeg;base64,")

    approved = client.put(f"/admin/agents/{agent.id}/kyc-approve", headers=admin_auth_headers)
    assert approved.status_code == 200, approved.text
    db_session.expire_all()
    updated_user = db_session.query(User).filter_by(id=user.id).one()
    updated_agent = db_session.query(Agent).filter_by(id=agent.id).one()
    updated_profile = db_session.query(AgentProfile).filter_by(user_id=user.id).one()
    assert updated_user.is_agent is True
    assert updated_agent.status == "active"
    assert updated_profile.kyc_status == "approved"
    assert updated_agent.float_balance > 0


def test_legacy_agent_approve_endpoint_cannot_bypass_kyc(client, db_session, admin_auth_headers):
    _user, agent = _create_paid_agent(db_session, user_id=8823, email="kyc-bypass@example.com")
    response = client.put(f"/admin/agents/{agent.id}/approve", headers=admin_auth_headers)
    assert response.status_code == 409
    db_session.expire_all()
    assert db_session.query(Agent).filter_by(id=agent.id).one().status == "pending_kyc"
