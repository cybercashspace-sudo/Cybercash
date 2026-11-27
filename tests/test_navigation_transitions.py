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

    def has_screen(self, name):
        return name in self.screens


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


def test_back_navigation_pops_history_without_home_fallback(monkeypatch):
    from core.navigation import navigate_back

    manager = _ScreenManager()
    manager.current = "transactions"
    manager.screens["register"] = SimpleNamespace(name="register")
    manager._cybercash_screen_history = ["home", "wallet"]
    monkeypatch.setattr(transitions, "_build_transition", lambda _style, _duration: SimpleNamespace(duration=0.12))
    monkeypatch.setattr(transitions, "_default_transition", lambda: SimpleNamespace(duration=0.12))
    monkeypatch.setattr(transitions.Clock, "schedule_once", lambda callback, timeout: _ScheduledEvent(callback, timeout))
    owner = SimpleNamespace(manager=manager, _active_dialog=None)

    assert navigate_back(owner) is True
    assert manager.current == "wallet"
    assert manager._cybercash_screen_history == ["home"]


def test_back_navigation_dismisses_popup_before_screen_change():
    from core.navigation import navigate_back

    calls = []
    dialog = SimpleNamespace(dismiss=lambda: calls.append("dismiss"))
    owner = SimpleNamespace(manager=None, _active_dialog=dialog)

    assert navigate_back(owner) is True
    assert calls == ["dismiss"]


def test_request_activity_keeps_busy_state_without_blocking_screen_with_spinner():
    import threading

    from core.responsive_screen import ResponsiveScreen

    class _Harness:
        screen_loading = False
        loading = True
        _request_activity_count = 0
        _request_activity_lock = threading.RLock()
        _REQUEST_BUSY_PROPERTIES = ResponsiveScreen._REQUEST_BUSY_PROPERTIES

    harness = _Harness()
    ResponsiveScreen._sync_request_activity(harness)
    assert harness.screen_loading is True

    harness.loading = False
    ResponsiveScreen._sync_request_activity(harness)
    assert harness.screen_loading is False


def test_request_overlay_spinner_has_been_removed():
    import core.responsive_screen as responsive_screen

    assert not hasattr(responsive_screen, "_RequestLoadingOverlay")


def test_pull_refresh_screens_show_overlay_from_existing_busy_flags():
    from core.pull_refresh import PullToRefreshMixin

    states = []

    class _Overlay:
        def set_active(self, active):
            states.append(bool(active))

    class _Harness:
        screen_loading = False
        loading = True
        _pull_request_overlay = _Overlay()
        _sync_pull_request_overlay = PullToRefreshMixin._sync_pull_request_overlay
        _screen_refresh_is_busy = lambda self: bool(self.loading)

    PullToRefreshMixin._sync_pull_request_overlay(_Harness())
    assert states == [True]


def test_terminal_action_feedback_becomes_one_popup_not_page_text(monkeypatch):
    from core import screen_actions

    scheduled = []

    class _Event:
        def __init__(self, callback):
            self.callback = callback
            self.cancelled = False

        def cancel(self):
            self.cancelled = True

    monkeypatch.setattr(
        screen_actions.Clock,
        "schedule_once",
        lambda callback, _timeout=0: scheduled.append(_Event(callback)) or scheduled[-1],
    )
    dialogs = []

    class _Harness:
        feedback_text = ""
        feedback_color = []
        _set_feedback = screen_actions.ActionScreen._set_feedback
        _show_feedback_popup = screen_actions.ActionScreen._show_feedback_popup
        _show_popup = lambda self, title, message: dialogs.append((title, message))

    screen = _Harness()
    screen._set_feedback("Transfer completed.", "success")
    assert screen.feedback_text == ""
    scheduled[0].callback(0)
    assert dialogs == [("Completed", "Transfer completed.")]
