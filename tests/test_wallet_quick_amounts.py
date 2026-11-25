from types import SimpleNamespace

from screens.wallet import KV, WalletScreen


class _QuickAmountHarness:
    DEPOSIT_QUICK_AMOUNTS = WalletScreen.DEPOSIT_QUICK_AMOUNTS
    WITHDRAW_QUICK_AMOUNTS = WalletScreen.WITHDRAW_QUICK_AMOUNTS
    MIN_PAYSTACK_DEPOSIT_GHS = 1.0
    ids = {
        "deposit_amount": SimpleNamespace(text=""),
        "transfer_amount": SimpleNamespace(text=""),
    }
    _parse_amount = staticmethod(WalletScreen._parse_amount)
    update_deposit_preview = WalletScreen.update_deposit_preview
    update_withdraw_preview = WalletScreen.update_withdraw_preview

    def __init__(self):
        self.deposit_ready = False
        self.deposit_button_text = "Pay with Paystack"
        self.deposit_preview = ""
        self.withdraw_fee_preview = ""
        self.selected_deposit_quick_amount = ""
        self.selected_withdraw_quick_amount = ""


def test_deposit_quick_amount_updates_field_preview_and_selection():
    screen = _QuickAmountHarness()

    WalletScreen.set_deposit_amount(screen, 50)

    assert screen.ids["deposit_amount"].text == "50"
    assert screen.deposit_ready is True
    assert screen.deposit_button_text == "Pay GHS 50.00 with Paystack"
    assert screen.deposit_preview == "You'll pay GHS 50.00 via Paystack."
    assert screen.selected_deposit_quick_amount == "50"


def test_withdraw_quick_amount_updates_fee_preview_and_selection():
    screen = _QuickAmountHarness()

    WalletScreen.set_withdraw_amount(screen, 20)

    assert screen.ids["transfer_amount"].text == "20"
    assert "Fee: GHS 0.20" in screen.withdraw_fee_preview
    assert "Total debit: GHS 20.20" in screen.withdraw_fee_preview
    assert screen.selected_withdraw_quick_amount == "20"


def test_manual_amount_edit_clears_quick_amount_highlight():
    screen = _QuickAmountHarness()
    WalletScreen.set_deposit_amount(screen, 10)

    WalletScreen.update_deposit_preview(screen, "10.50")

    assert screen.selected_deposit_quick_amount == ""
    assert "GHS 10.50" in screen.deposit_preview


def test_quick_amount_buttons_bind_selection_highlighting():
    assert 'root.selected_deposit_quick_amount == "50"' in KV
    assert 'root.selected_withdraw_quick_amount == "20"' in KV
