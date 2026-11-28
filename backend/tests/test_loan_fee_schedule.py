from decimal import Decimal

import pytest

from backend.core.security import create_access_token
from backend.models import Loan, User, Wallet
from backend.services.loan_service import loan_fee_percentage_for_duration
from utils.security import hash_pin


@pytest.mark.parametrize(
    ("days", "expected_rate"),
    [(1, "0.50"), (7, "3.50"), (14, "7.00"), (30, "15.00"), (60, "30.00"), (90, "45.00")],
)
def test_loan_fee_rate_is_prorated_from_thirty_day_base(days, expected_rate):
    assert loan_fee_percentage_for_duration(days) == Decimal(expected_rate)


def test_loan_policy_returns_fee_rate_for_each_available_term(client, db_session):
    user = User(
        email="loan-policy@example.test",
        password_hash=hash_pin("1234"),
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    headers = {"Authorization": f"Bearer {create_access_token(data={'sub': str(user.id)})}"}

    response = client.get("/loans/my-policy", headers=headers)

    assert response.status_code == 200, response.text
    policy = response.json()
    assert policy["fee_rate_base_period_days"] == 30
    assert policy["period_fee_percentages"] == {"1": 0.5, "7": 3.5, "14": 7.0, "30": 15.0}


@pytest.mark.parametrize(("days", "expected_fee"), [(1, "0.50"), (7, "3.50"), (14, "7.00"), (30, "15.00")])
def test_disbursed_loan_uses_selected_term_fee_rate(client, db_session, days, expected_fee):
    user = User(
        email=f"loan-{days}-day@example.test",
        password_hash=hash_pin("1234"),
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.add(Wallet(user_id=user.id, currency="GHS", balance=0))
    db_session.commit()
    headers = {"Authorization": f"Bearer {create_access_token(data={'sub': str(user.id)})}"}

    response = client.post(
        "/loans/apply",
        json={"amount": 100, "repayment_duration": days, "purpose": "test"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    loan = db_session.query(Loan).filter_by(user_id=user.id).one()
    assert Decimal(str(loan.base_fee_percentage)) == Decimal(expected_fee)
    assert Decimal(str(loan.base_fee_amount)) == Decimal(expected_fee)
    assert Decimal(str(loan.outstanding_balance)) == Decimal("100.00") + Decimal(expected_fee)
