from types import SimpleNamespace

from core.popup_manager import _bind_popup_lifecycle, _owner_is_active, show_message_dialog


def test_owner_is_active_only_for_current_managed_screen():
    current = SimpleNamespace(name="home")
    manager = SimpleNamespace(current="home", current_screen=current)
    current.manager = manager
    assert _owner_is_active(current) is True
    assert _owner_is_active(SimpleNamespace(name="loans", manager=manager)) is False


def test_stale_screen_response_does_not_open_popup():
    current = SimpleNamespace(name="home")
    manager = SimpleNamespace(current="home", current_screen=current)
    owner = SimpleNamespace(name="loans", manager=manager, _active_dialog=None)

    result = show_message_dialog(owner, title="Loan Update", message="Refresh failed.")

    assert result is None
    assert owner._active_dialog is None


def test_open_popup_is_dismissed_and_unbound_when_screen_leaves():
    class Owner:
        manager = None

        def __init__(self):
            self._active_dialog = None
            self.listeners = []

        def bind(self, **kwargs):
            self.listeners.append(kwargs["on_leave"])

        def unbind(self, **kwargs):
            listener = kwargs.get("on_leave")
            self.listeners = [item for item in self.listeners if item != listener]

    class Dialog:
        def bind(self, **kwargs):
            self.on_dismiss = kwargs["on_dismiss"]

        def dismiss(self):
            self.on_dismiss()

    owner = Owner()
    dialog = Dialog()
    owner._active_dialog = dialog
    _bind_popup_lifecycle(owner, dialog)

    for listener in tuple(owner.listeners):
        listener()

    assert owner._active_dialog is None
    assert owner.listeners == []
