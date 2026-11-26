from pathlib import Path
from types import SimpleNamespace


def test_airtime_cash_screen_is_compact_and_keeps_generation_actions():
    from screens.airtime_cash import KV

    assert 'text: "Generate Number"' in KV
    assert 'text: "Airtime Sent"' in KV
    assert 'text: "Estimated cash payout"' in KV
    assert 'text: "How it works"' not in KV
    assert 'root.transfer_instructions' not in KV
    assert 'root.flow_hint' not in KV
    assert 'disabled: root.loading' in KV
    assert KV.count('BottomNavBar:') == 1


def test_airtime_cash_generate_number_submits_validated_quote(monkeypatch):
    from screens import airtime_cash

    class _Field:
        text = "0241234567"

    captured = []

    class _Harness:
        loading = False
        payout_rate = 0.8
        selected_network = ""
        ids = {"phone_input": _Field(), "amount_input": SimpleNamespace(text="20")}
        _parse_amount = airtime_cash.AirtimeCashScreen._parse_amount
        _update_estimate = airtime_cash.AirtimeCashScreen._update_estimate
        _set_selected_network = airtime_cash.AirtimeCashScreen._set_selected_network
        _generate_merchant_number_worker = airtime_cash.AirtimeCashScreen._generate_merchant_number_worker
        _start_request = lambda self, *args: captured.append(args)

    monkeypatch.setattr(airtime_cash, "normalize_ghana_number", lambda value: value)
    monkeypatch.setattr(airtime_cash, "detect_network", lambda _value: "MTN")
    screen = _Harness()
    airtime_cash.AirtimeCashScreen.generate_merchant_number(screen)

    assert captured and captured[0][0] == "Requesting merchant number..."
    assert captured[0][1].__name__ == "_generate_merchant_number_worker"
    assert captured[0][2:] == ("0241234567", "MTN", 20.0)


def test_airtime_cash_shows_backend_generated_number_in_one_popup():
    from screens.airtime_cash import AirtimeCashScreen

    calls = []

    class _Harness:
        sale_id = ""
        merchant_number = ""
        payout_rate = 0.8
        ids = {"amount_input": SimpleNamespace(text="20")}
        _parse_amount = AirtimeCashScreen._parse_amount
        _is_current_request = lambda self, _request_id: True
        _set_sale_status = lambda self, status: setattr(self, "sale_status_display", str(status).replace("_", " ").title())
        _update_estimate = AirtimeCashScreen._update_estimate
        _set_feedback = lambda self, message, level: calls.append(("feedback", message, level))
        _show_popup = lambda self, title, message: calls.append(("popup", title, message))
        _set_loading = lambda self, value: calls.append(("loading", value))

    screen = _Harness()
    AirtimeCashScreen._apply_merchant_number_result(
        screen,
        1,
        True,
        {"sale_id": "sale-12345678", "merchant_number": "0551234567", "payout_rate": 0.8, "status": "pending"},
        20.0,
        "0241234567",
        "MTN",
    )

    popups = [item for item in calls if item[0] == "popup"]
    assert screen.merchant_number == "0551234567"
    assert len(popups) == 1
    assert "0551234567" in popups[0][2]
    assert "GHS 16.00" in popups[0][2]
