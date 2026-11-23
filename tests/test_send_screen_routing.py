from __future__ import annotations

import os
import tempfile

os.environ.setdefault("KIVY_HOME", tempfile.mkdtemp(prefix="cybercash-kivy-test-"))

from kivy_app import SCREEN_SPECS
from features.transfer.transfer_screen import TransferScreen
from screens.p2p_transfer import P2PTransferScreen


def test_dashboard_send_route_uses_the_apk_p2p_transfer_screen():
    assert SCREEN_SPECS["p2p_transfer"] == ("screens.p2p_transfer", "P2PTransferScreen")
    assert TransferScreen is P2PTransferScreen
