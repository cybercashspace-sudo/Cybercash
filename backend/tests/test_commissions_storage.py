from backend.core.security import create_access_token
from backend.models import Agent, Commission, User, Wallet


def test_agent_deposit_persists_commission_row(client, db_session):
    agent_user = User(email="commission_agent@test.com", password_hash="hash", is_active=True, is_verified=True, is_agent=True)
    customer = User(email="commission_customer@test.com", password_hash="hash", is_active=True, is_verified=True)
    db_session.add_all([agent_user, customer])
    db_session.commit()
    db_session.refresh(agent_user)
    db_session.refresh(customer)

    db_session.add(Wallet(user_id=agent_user.id, balance=0.0))
    db_session.add(Wallet(user_id=customer.id, balance=10.0))
    db_session.add(
        Agent(
            user_id=agent_user.id,
            status="active",
            commission_rate=0.02,
            float_balance=1000.0,
            commission_balance=0.0,
        )
    )
    db_session.commit()

    headers = {"Authorization": f"Bearer {create_access_token(data={'sub': agent_user.email})}"}
    response = client.post(
        "/agent-transactions/cash-deposit",
        json={"customer_email": customer.email, "amount": 500.0, "currency": "GHS"},
        headers=headers,
    )
    assert response.status_code == 201

    rows = db_session.query(Commission).all()
    assert len(rows) >= 1
    positive = [r for r in rows if r.amount > 0]
    assert len(positive) >= 1
    assert positive[0].commission_type.endswith("_COMMISSION")
