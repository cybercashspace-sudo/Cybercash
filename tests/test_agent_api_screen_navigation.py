from kivy_app import SCREEN_SPECS


def test_agent_dashboard_opens_the_dedicated_api_screen():
    from pathlib import Path
    from features.agent import agent_api_screen

    dashboard_kv = Path("features/agent/agent_dashboard.kv").read_text(encoding="utf-8")
    api_kv = Path("features/agent/agent_api_screen.kv").read_text(encoding="utf-8")

    assert SCREEN_SPECS["agent_api"] == ("features.agent.agent_api_screen", "AgentApiScreen")
    assert "root.open_api_screen()" in dashboard_kv
    assert api_kv.count("BottomNavBar:") == 1
    assert 'nav_variant: "agent"' in api_kv
    assert 'text: "Back"' in api_kv
    assert "on_release: root.go_back()" in api_kv
    assert "root.generate_api_key()" in api_kv
    assert agent_api_screen.AgentApiScreen.__name__ == "AgentApiScreen"


def test_send_balance_requires_a_valid_live_backend_value():
    from screens.p2p_transfer import P2PTransferScreen

    class _Harness:
        _wallet_loading = True
        balance_display = "GHS 0.00"
        wallet_status = "Updating balance..."
        wallet_is_live = False

        _number = staticmethod(P2PTransferScreen._number)
        _show_auth_required = lambda self, _message: None
        _set_feedback = lambda self, *_args: None
        _show_popup = lambda self, *_args: None

    screen = _Harness()
    P2PTransferScreen._apply_wallet_result(screen, True, {"balance": 42.5})
    assert screen.balance_display == "GHS 42.50"
    assert screen.wallet_status == "Live balance"
    assert screen.wallet_is_live is True

    P2PTransferScreen._apply_wallet_result(screen, True, {"balance": None})
    assert screen.wallet_is_live is False
    assert screen.wallet_status == "Balance unavailable · Tap Refresh"


def test_send_is_blocked_until_a_live_balance_has_loaded():
    from screens.p2p_transfer import P2PTransferScreen

    events = []

    class _Harness:
        transfer_busy = False
        wallet_is_live = False

        _show_popup = lambda self, title, message: events.append((title, message))

    P2PTransferScreen.send_funds(_Harness())

    assert len(events) == 1
    assert events[0][0] == "Balance unavailable"


def test_live_wallet_load_uses_the_authenticated_wallet_endpoint_and_short_timeout(monkeypatch):
    from screens import p2p_transfer
    from screens.p2p_transfer import P2PTransferScreen

    calls = []

    class _Harness:
        _wallet_loading = True
        balance_display = "GHS 0.00"
        wallet_status = "Updating balance..."
        wallet_is_live = False
        _number = staticmethod(P2PTransferScreen._number)
        _apply_wallet_result = P2PTransferScreen._apply_wallet_result
        _show_auth_required = lambda self, _message: None
        _set_feedback = lambda self, *_args: None
        _show_popup = lambda self, *_args: None

        def _request(self, method, path, **kwargs):
            calls.append((method, path, kwargs))
            return True, {"balance": 27.5}

    monkeypatch.setattr(p2p_transfer.Clock, "schedule_once", lambda callback, *_args: callback(0))
    screen = _Harness()
    P2PTransferScreen._load_wallet_worker(screen, notify=False)

    assert calls == [("GET", "/wallet/me", {"timeout": (4, 8)})]
    assert screen.balance_display == "GHS 27.50"
    assert screen.wallet_is_live is True


def test_transfer_fee_response_is_applied_on_the_ui_clock(monkeypatch):
    from screens import p2p_transfer
    from screens.p2p_transfer import P2PTransferScreen

    applied = []

    class _Harness:
        def _request(self, method, path):
            return True, {"p2p_free_remaining": 100}

        def _apply_fee_status(self, ok, payload, notify):
            applied.append((ok, payload, notify))

    monkeypatch.setattr(p2p_transfer.Clock, "schedule_once", lambda callback, *_args: callback(0))
    P2PTransferScreen._load_fee_status_worker(_Harness(), notify=False)

    assert applied == [(True, {"p2p_free_remaining": 100}, False)]
