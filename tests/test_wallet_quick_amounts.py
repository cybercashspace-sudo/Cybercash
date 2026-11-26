from screens.wallet import KV, WalletScreen


class _TextField:
    def __init__(self, on_text=None):
        self._text = ""
        self._on_text = on_text

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        self._text = str(value)
        if self._on_text:
            self._on_text(self._text)


class _QuickAmountHarness:
    DEPOSIT_QUICK_AMOUNTS = WalletScreen.DEPOSIT_QUICK_AMOUNTS
    WITHDRAW_QUICK_AMOUNTS = WalletScreen.WITHDRAW_QUICK_AMOUNTS
    MIN_PAYSTACK_DEPOSIT_GHS = 1.0
    _parse_amount = staticmethod(WalletScreen._parse_amount)
    update_deposit_preview = WalletScreen.update_deposit_preview
    on_withdraw_amount_changed = WalletScreen.on_withdraw_amount_changed

    def update_withdraw_preview(self, raw_amount):
        self.preview_update_count += 1
        return WalletScreen.update_withdraw_preview(self, raw_amount)

    def __init__(self):
        self._setting_withdraw_quick_amount = False
        self.preview_update_count = 0
        self.ids = {
            "deposit_amount": _TextField(self.update_deposit_preview),
            "transfer_amount": _TextField(self.on_withdraw_amount_changed),
        }
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


def test_manual_withdraw_amount_edit_updates_preview_and_clears_selection():
    screen = _QuickAmountHarness()
    WalletScreen.set_withdraw_amount(screen, 20)

    screen.ids["transfer_amount"].text = "20.50"

    assert screen.selected_withdraw_quick_amount == ""
    assert "Total debit: GHS 20.71" in screen.withdraw_fee_preview


def test_invalid_quick_amounts_do_not_change_fields_or_previews():
    screen = _QuickAmountHarness()
    WalletScreen.set_deposit_amount(screen, 10)
    before_preview = screen.deposit_preview

    WalletScreen.set_deposit_amount(screen, float("nan"))
    WalletScreen.set_withdraw_amount(screen, 999)

    assert screen.ids["deposit_amount"].text == "10"
    assert screen.deposit_preview == before_preview
    assert screen.ids["transfer_amount"].text == ""
    assert WalletScreen._parse_amount("nan") == 0.0


def test_quick_amount_buttons_bind_selection_highlighting():
    assert 'root.selected_deposit_quick_amount == "50"' in KV
    assert 'root.selected_withdraw_quick_amount == "20"' in KV


def test_every_withdraw_quick_amount_updates_the_amount_and_fee_preview():
    screen = _QuickAmountHarness()

    for amount in WalletScreen.WITHDRAW_QUICK_AMOUNTS:
        screen.preview_update_count = 0
        WalletScreen.set_withdraw_amount(screen, amount)

        assert screen.preview_update_count == 1
        fee = round(amount * 0.01, 2)
        total = round(amount + fee, 2)
        assert screen.ids["transfer_amount"].text == str(amount)
        assert screen.selected_withdraw_quick_amount == str(amount)
        assert f"Fee: GHS {fee:,.2f}" in screen.withdraw_fee_preview
        assert f"Total debit: GHS {total:,.2f}" in screen.withdraw_fee_preview


def test_wallet_modes_share_one_apk_dashboard_bottom_navigation():
    assert KV.count("BottomNavBar:") == 1
    assert 'nav_variant: "dashboard"' in KV
