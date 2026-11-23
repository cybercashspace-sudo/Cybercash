from __future__ import annotations

import os
import tempfile

os.environ.setdefault("KIVY_HOME", tempfile.mkdtemp(prefix="cybercash-kivy-test-"))

from kivy_app import SCREEN_SPECS
from features.deposit.deposit_screen import DepositScreen as FeatureDepositScreen
from screens.wallet import DepositScreen as WalletDepositScreen


def test_dashboard_deposit_route_uses_the_apk_wallet_deposit_screen():
    assert SCREEN_SPECS["deposit"] == ("screens.wallet", "DepositScreen")
    assert FeatureDepositScreen is WalletDepositScreen
