from backend.models import BundleCatalog, User


def _auth_headers_for_user(user):
    from backend.core.security import create_access_token

    token = create_access_token(data={"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def test_bundle_catalog_lists_active_only(client, db_session):
    user = User(email="bundles_list@test.com", password_hash="hash", is_active=True, is_verified=True)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    db_session.add_all(
        [
            BundleCatalog(network="MTN", bundle_code="MTN-1GB", amount=5.0, currency="GHS", is_active=True),
            BundleCatalog(network="MTN", bundle_code="MTN-2GB", amount=9.0, currency="GHS", is_active=False),
            BundleCatalog(network="VODAFONE", bundle_code="VODA-500MB", amount=3.0, currency="GHS", is_active=True),
        ]
    )
    db_session.commit()

    response = client.get("/api/bundles/catalog", headers=_auth_headers_for_user(user))
    assert response.status_code == 200
    data = response.json()
    assert any(item["bundle_code"] == "MTN-1GB" for item in data)
    assert any(item["bundle_code"] == "VODA-500MB" for item in data)
    assert all(item["bundle_code"] != "MTN-2GB" for item in data)


def test_bundle_catalog_filters_by_network(client, db_session):
    user = User(email="bundles_filter@test.com", password_hash="hash", is_active=True, is_verified=True)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    db_session.add_all(
        [
            BundleCatalog(network="MTN", bundle_code="MTN-5GB", amount=20.0, currency="GHS", is_active=True),
            BundleCatalog(network="AIRTELTIGO", bundle_code="AT-1GB", amount=4.0, currency="GHS", is_active=True),
        ]
    )
    db_session.commit()

    response = client.get("/api/bundles/catalog?network=mtn", headers=_auth_headers_for_user(user))
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["network"] == "MTN"
    assert data[0]["bundle_code"] == "MTN-5GB"
