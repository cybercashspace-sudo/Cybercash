from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.database import Base, engine
from backend.main import app
from backend.dependencies.auth import get_current_user
from backend.models import User, Wallet, Transaction, Agent
from backend.schemas.wallet import WalletResponse
from unittest.mock import patch
import pytest

# Use a test database
@pytest.fixture(scope="module")
def test_db():
    # Schema setup handled by conftest
    db = Session(bind=engine)
    yield db
    db.close()
    # Schema teardown handled by conftest

# Override get_current_user for testing admin endpoints
def override_get_current_admin_user():
    return User(id=400, email="admin_test@example.com", full_name="Admin Test", is_active=True, is_verified=True, is_admin=True)

def override_get_current_normal_user():
    return User(id=401, email="normal_test@example.com", full_name="Normal Test", is_active=True, is_verified=True, is_admin=False)

client = TestClient(app)


@pytest.fixture
def as_admin():
    app.dependency_overrides[get_current_user] = override_get_current_admin_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def as_normal_user():
    app.dependency_overrides[get_current_user] = override_get_current_normal_user
    yield
    app.dependency_overrides.pop(get_current_user, None)

@pytest.fixture(autouse=True)
def setup_admin_test_data(test_db: Session):
    # Clean state
    test_db.query(Transaction).delete()
    test_db.query(Wallet).delete()
    test_db.query(Agent).delete()
    test_db.query(User).delete()
    test_db.commit()

    admin_user = User(id=400, email="admin_test@example.com", full_name="Admin Test", password_hash="hashed_password", is_active=True, is_verified=True, is_admin=True)
    normal_user = User(id=401, email="normal_test@example.com", full_name="Normal Test", password_hash="hashed_password", is_active=True, is_verified=True, is_admin=False)
    test_db.add_all([admin_user, normal_user])
    test_db.commit()
    test_db.refresh(admin_user)
    test_db.refresh(normal_user)

    normal_user_wallet = Wallet(user_id=normal_user.id, currency="GHS", balance=150.0)
    admin_user_wallet = Wallet(user_id=admin_user.id, currency="GHS", balance=500.0)
    test_db.add_all([normal_user_wallet, admin_user_wallet])
    test_db.commit()
    test_db.refresh(normal_user_wallet)
    test_db.refresh(admin_user_wallet)

    transaction1 = Transaction(user_id=normal_user.id, wallet_id=normal_user_wallet.id, type="deposit", amount=100.0, currency="GHS", status="completed")
    transaction2 = Transaction(user_id=normal_user.id, wallet_id=normal_user_wallet.id, type="transfer_send", amount=50.0, currency="GHS", status="completed")
    transaction3 = Transaction(user_id=admin_user.id, wallet_id=admin_user_wallet.id, type="deposit", amount=500.0, currency="GHS", status="completed")
    test_db.add_all([transaction1, transaction2, transaction3])
    test_db.commit()
    
    yield
    test_db.query(Transaction).delete()
    test_db.query(Wallet).delete()
    test_db.query(Agent).delete()
    test_db.query(User).delete()
    test_db.commit()


def test_get_user_wallet_admin_success(test_db: Session, as_admin):
    response = client.get(f"/admin/users/401/wallet")
    assert response.status_code == 200
    wallet_data = response.json()
    assert wallet_data["user_id"] == 401
    assert wallet_data["balance"] == 150.0

def test_get_user_wallet_admin_not_found(test_db: Session, as_admin):
    response = client.get(f"/admin/users/999/wallet")
    assert response.status_code == 404
    assert "User wallet not found." in response.json()["detail"]

def test_get_user_wallet_admin_forbidden(test_db: Session, as_normal_user):
    response = client.get(f"/admin/users/401/wallet")
    assert response.status_code == 403
    assert "Only administrators can perform this action" in response.json()["detail"]


def test_get_all_wallets_admin_success(test_db: Session, as_admin):
    response = client.get("/admin/wallets")
    assert response.status_code == 200
    wallets_data = response.json()
    assert len(wallets_data) == 2
    user_ids = {w["user_id"] for w in wallets_data}
    assert 400 in user_ids
    assert 401 in user_ids

def test_get_all_wallets_admin_forbidden(test_db: Session, as_normal_user):
    response = client.get("/admin/wallets")
    assert response.status_code == 403
    assert "Only administrators can perform this action" in response.json()["detail"]


def test_get_all_transactions_admin_no_filters(test_db: Session, as_admin):
    response = client.get("/admin/transactions")
    assert response.status_code == 200
    transactions_data = response.json()
    assert len(transactions_data) == 3

def test_get_all_transactions_admin_filter_by_user_id(test_db: Session, as_admin):
    response = client.get("/admin/transactions?user_id=401")
    assert response.status_code == 200
    transactions_data = response.json()
    assert len(transactions_data) == 2
    for tx in transactions_data:
        assert tx["user_id"] == 401

def test_get_all_transactions_admin_filter_by_type(test_db: Session, as_admin):
    response = client.get("/admin/transactions?type=deposit")
    assert response.status_code == 200
    transactions_data = response.json()
    assert len(transactions_data) == 2
    for tx in transactions_data:
        assert tx["type"] == "deposit"

def test_get_all_transactions_admin_filter_by_status(test_db: Session, as_admin):
    response = client.get("/admin/transactions?status=completed")
    assert response.status_code == 200
    transactions_data = response.json()
    assert len(transactions_data) == 3
    for tx in transactions_data:
        assert tx["status"] == "completed"

def test_get_all_transactions_admin_forbidden(test_db: Session, as_normal_user):
    response = client.get("/admin/transactions")
    assert response.status_code == 403
    assert "Only administrators can perform this action" in response.json()["detail"]


def test_suspended_admin_can_still_access_admin_endpoints(test_db: Session, admin_auth_headers):
    admin_user = test_db.query(User).filter(User.id == 400).first()
    assert admin_user is not None
    admin_user.status = "suspended"
    admin_user.is_active = False
    test_db.commit()

    response = client.get("/admin/wallets", headers=admin_auth_headers)
    assert response.status_code == 200
    wallets_data = response.json()
    assert len(wallets_data) == 2


def test_admin_account_cannot_be_suspended(test_db: Session, admin_auth_headers):
    response = client.put(
        "/admin/users/400/status",
        headers=admin_auth_headers,
        json={"status": "suspended"},
    )
    assert response.status_code == 403
    assert "Admin accounts cannot be suspended" in response.json()["detail"]
