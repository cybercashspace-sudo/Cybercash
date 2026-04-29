from backend.models import Agent, CryptoWallet, User


def _ussd_request(client, *, phone_number: str, text: str = "", session_id: str = "S1"):
    return client.post(
        "/ussd",
        data={
            "phoneNumber": phone_number,
            "sessionId": session_id,
            "serviceCode": "*360#",
            "text": text,
        },
    )


def _create_user(db_session, *, phone_number: str, is_agent: bool = False) -> User:
    user = User(
        email=f"{phone_number}@test.com",
        phone_number=phone_number,
        momo_number=phone_number,
        password_hash="hash",
        is_active=True,
        is_verified=True,
        is_agent=is_agent,
        role="agent" if is_agent else "user",
        status="active",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _set_active_agent(db_session, user: User) -> Agent:
    agent = Agent(
        user_id=user.id,
        status="active",
        commission_rate=0.02,
        float_balance=250.0,
        commission_balance=12.5,
        loan_auto_deduction_enabled=True,
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


def _set_btc_wallet(db_session, user: User, *, balance: float) -> CryptoWallet:
    wallet = CryptoWallet(
        user_id=user.id,
        coin_type="BTC",
        address=f"btc_addr_{user.id}",
        balance=balance,
    )
    db_session.add(wallet)
    db_session.commit()
    db_session.refresh(wallet)
    return wallet


def test_ussd_main_menu_includes_agent_shortcut(client, db_session):
    user = _create_user(db_session, phone_number="0241001000", is_agent=True)
    _set_active_agent(db_session, user)

    response = _ussd_request(client, phone_number="0241001000")

    assert response.status_code == 200
    assert response.text.startswith("CON")
    assert "Cyber Cash (*360#)" in response.text
    assert "1. Balance" in response.text
    assert "8. BTC Balance" in response.text
    assert "9. Agent" in response.text


def test_ussd_zero_returns_to_main_menu(client, db_session):
    user = _create_user(db_session, phone_number="0241001001", is_agent=True)
    _set_active_agent(db_session, user)

    submenu_response = _ussd_request(client, phone_number="0241001001", text="2")
    assert "0. Back to Menu" in submenu_response.text

    back_response = _ussd_request(client, phone_number="0241001001", text="2*0")

    assert back_response.status_code == 200
    assert "Cyber Cash (*360#)" in back_response.text
    assert "1. Balance" in back_response.text
    assert "8. BTC Balance" in back_response.text
    assert "9. Agent" in back_response.text


def test_ussd_btc_balance_menu_shows_ghs_value(client, db_session, monkeypatch):
    user = _create_user(db_session, phone_number="0241001003", is_agent=False)
    _set_btc_wallet(db_session, user, balance=0.5)

    class _FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def _fake_get(url, timeout=None):
        return _FakeResponse({"lastPrice": "60000"})

    monkeypatch.setattr("backend.routes.ussd.requests.get", _fake_get, raising=True)

    response = _ussd_request(client, phone_number="0241001003", text="8")

    assert response.status_code == 200
    assert response.text.startswith("CON")
    assert "BTC Balance" in response.text
    assert "Holdings: 0.50000000 BTC" in response.text
    assert "Value: GHS 360,000.00" in response.text


def test_ussd_agent_shortcut_toggles_loan_sweep(client, db_session):
    user = _create_user(db_session, phone_number="0241001002", is_agent=True)
    db_session.add(
        Agent(
            user_id=user.id,
            status="active",
            commission_rate=0.02,
            float_balance=250.0,
            commission_balance=12.5,
            loan_auto_deduction_enabled=True,
        )
    )
    db_session.commit()

    menu_response = _ussd_request(client, phone_number="0241001002", text="9")
    assert "1. Summary" in menu_response.text
    assert "2. Loan Sweep" in menu_response.text
    assert "3. Loan Status" in menu_response.text

    sweep_menu = _ussd_request(client, phone_number="0241001002", text="9*2")
    assert "Current: On" in sweep_menu.text
    assert "1. Turn On" in sweep_menu.text
    assert "2. Turn Off" in sweep_menu.text

    sweep_update = _ussd_request(client, phone_number="0241001002", text="9*2*2")
    assert "Loan Sweep Updated" in sweep_update.text
    assert "State: Off" in sweep_update.text

    refreshed_agent = db_session.query(Agent).filter(Agent.user_id == user.id).first()
    assert refreshed_agent is not None
    assert refreshed_agent.loan_auto_deduction_enabled is False
