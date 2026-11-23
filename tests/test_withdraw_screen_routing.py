from __future__ import annotations

import os
import tempfile

os.environ.setdefault("KIVY_HOME", tempfile.mkdtemp(prefix="cybercash-kivy-test-"))

from kivy_app import SCREEN_SPECS
from features.withdrawal.withdrawal_screen import WithdrawalScreen
from screens.wallet import WithdrawScreen


def test_dashboard_withdraw_route_uses_the_apk_wallet_withdraw_screen():
    assert SCREEN_SPECS["withdraw"] == ("screens.wallet", "WithdrawScreen")
    assert WithdrawalScreen is WithdrawScreen
