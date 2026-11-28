from pathlib import Path
from types import SimpleNamespace

from kivymd.app import MDApp

from core.bottom_nav import BottomNavBar
from features.bitcoin import bitcoin_screen as bitcoin_module
from kivy_app import SCREEN_SPECS


def test_send_screen_uses_short_copy_and_single_shared_bottom_navigation():
    from screens.p2p_transfer import KV as send_kv

    assert SCREEN_SPECS["p2p_transfer"] == ("screens.p2p_transfer", "P2PTransferScreen")
    assert 'text: "Send Money"' in send_kv
    assert 'text: "GHS 100 daily free; 0.5% fee above the limit."' in send_kv
    assert 'root.feedback_hint' not in send_kv
    assert send_kv.count("BottomNavBar:") == 1
    assert 'nav_variant: "send"' in send_kv
    assert 'active_target: "p2p_transfer"' in send_kv
    assert 'on_release: root.go_back()' in send_kv


def test_send_preview_is_concise_and_preserves_fee_total():
    from screens.p2p_transfer import P2PTransferScreen

    class _Harness:
        _p2p_free_remaining = 100.0
        transfer_preview = ""
        _parse_amount = staticmethod(P2PTransferScreen._parse_amount)
        update_transfer_preview = P2PTransferScreen.update_transfer_preview

    screen = _Harness()
    screen.update_transfer_preview("150")
    assert screen.transfer_preview == "Recipient gets GHS 150.00 | fee GHS 0.25 | total GHS 150.25"


def test_send_wallet_load_is_dispatched_off_the_ui_thread(monkeypatch):
    from screens import p2p_transfer

    started = []

    class _Thread:
        def __init__(self, *, target, args, daemon):
            started.append((target, args, daemon))

        def start(self):
            started[-1] = (*started[-1], "started")

    class _Harness:
        _wallet_loading = False
        _load_wallet_worker = p2p_transfer.P2PTransferScreen._load_wallet_worker

    monkeypatch.setattr(p2p_transfer.threading, "Thread", _Thread)
    p2p_transfer.P2PTransferScreen.load_wallet(_Harness())

    assert started and started[0][0].__name__ == "_load_wallet_worker"
    assert started[0][-1] == "started"


def test_btc_screen_has_back_and_airtime_bottom_navigation():
    kv = Path(bitcoin_module.__file__).with_name("bitcoin_screen.kv").read_text(encoding="utf-8")

    assert kv.count("BottomNavBar:") == 1
    assert 'nav_variant: "default"' in kv
    assert 'text: "Back"' in kv
    assert 'on_release: root.go_back()' in kv
    assert 'from core.screen_actions import ActionScreen' in Path(bitcoin_module.__file__).read_text(encoding="utf-8")


def test_cards_bottom_nav_item_routes_to_registered_card_screen(monkeypatch):
    cards_item = next(item for item in BottomNavBar._variants["default"] if item["label"] == "Cards")
    assert cards_item["target"] == "virtual_card"
    assert SCREEN_SPECS[cards_item["target"]] == ("screens.cards", "VirtualCardScreen")

    calls = []
    app = SimpleNamespace(
        root=SimpleNamespace(current="btc"),
        go_to_screen=lambda target, **kwargs: calls.append((target, kwargs)) or True,
    )

    class _NavHarness:
        _navigate = BottomNavBar._navigate

        @staticmethod
        def _sync_selection_to_current_screen():
            pass

    monkeypatch.setattr(MDApp, "get_running_app", staticmethod(lambda: app))
    monkeypatch.setattr("core.bottom_nav.tap_feedback", lambda: None)
    _NavHarness()._navigate(cards_item["target"])

    assert calls and calls[0][0] == "virtual_card"


def test_cards_bottom_nav_hit_target_includes_icon_and_label():
    from kivy.uix.behaviors import ButtonBehavior
    from core.bottom_nav import _BottomNavItem

    assert ButtonBehavior in _BottomNavItem.__mro__
