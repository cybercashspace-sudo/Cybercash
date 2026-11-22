from __future__ import annotations

from types import SimpleNamespace

from components import transitions


class _ScheduledEvent:
    def __init__(self, callback, timeout):
        self.callback = callback
        self.timeout = timeout
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class _ScreenManager:
    def __init__(self):
        self.screens = {
            "home": SimpleNamespace(name="home"),
            "wallet": SimpleNamespace(name="wallet"),
            "transactions": SimpleNamespace(name="transactions"),
        }
        self.current = "home"
        self.transition = None

    @property
    def current_screen(self):
        return self.screens.get(self.current)

    def get_screen(self, name):
        return self.screens[name]


def test_transition_lock_uses_actual_duration_and_resets_default(monkeypatch):
    manager = _ScreenManager()
    requested_transitions = []

    def build_transition(style, duration):
        requested_transitions.append((style, duration))
        return SimpleNamespace(duration=0.14)

    monkeypatch.setattr(transitions, "_build_transition", build_transition)
    monkeypatch.setattr(
        transitions,
        "_default_transition",
        lambda: SimpleNamespace(duration=transitions.DEFAULT_TRANSITION_DURATION),
    )
    monkeypatch.setattr(
        transitions.Clock,
        "schedule_once",
        lambda callback, timeout: _ScheduledEvent(callback, timeout),
    )

    assert transitions.smooth_switch_screen(
        manager,
        "wallet",
        style="slide_left",
        duration=1.0,
    )
    restore_event = manager._cybercash_restore_event
    assert manager.current == "wallet"
    assert manager._cybercash_nav_busy is True
    assert restore_event.timeout == 0.16

    # A rapid second tap is ignored while the first transition is active.
    assert not transitions.smooth_switch_screen(manager, "transactions")
    assert manager._cybercash_pending_target == "wallet"

    restore_event.callback(0.16)
    assert manager._cybercash_nav_busy is False
    assert manager._cybercash_pending_target == ""
    assert manager.transition.duration == transitions.DEFAULT_TRANSITION_DURATION
    assert requested_transitions == [("slide_left", 1.0)]
