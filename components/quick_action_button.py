from __future__ import annotations

from .quick_action import QuickAction


class QuickActionButton(QuickAction):
    """Compatibility alias for the reusable dashboard quick-action tile."""


try:
    from kivy.factory import Factory

    Factory.register("QuickActionButton", cls=QuickActionButton)
except Exception:
    pass
