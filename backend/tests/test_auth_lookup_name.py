from backend.models import User


def test_lookup_name_returns_registered_first_name(client, db_session):
    user = User(
        momo_number="0241234567",
        phone_number="0241234567",
        full_name="John Doe",
        pin_hash="hash",
        password_hash="hash",
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()

    response = client.post("/auth/lookup-name", json={"momo_number": "0241234567"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["registered"] is True
    assert payload["first_name"] == "John"
    assert payload["display_name"] == "John"
    assert payload["network"] == "MTN"
    assert payload["is_verified"] is True


def test_lookup_name_returns_network_fallback_for_unknown_number(client):
    response = client.post("/auth/lookup-name", json={"momo_number": "0201234567"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["registered"] is False
    assert payload["first_name"] == ""
    assert payload["network"] == "TELECEL"
    assert payload["display_name"] == "Telecel User"
    assert payload["is_verified"] is False
