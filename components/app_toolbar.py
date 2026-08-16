from __future__ import annotations

from core.kivymd_compat import resolve_kivymd_top_app_bar
from theme import SURFACE, TEXT_PRIMARY


MDTopAppBar = resolve_kivymd_top_app_bar()


class AppToolbar(MDTopAppBar):
    """Shared top app bar with CYBER CASH styling."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.elevation = 0
        if hasattr(self, "md_bg_color"):
            self.md_bg_color = list(SURFACE)
        if hasattr(self, "specific_text_color"):
            self.specific_text_color = list(TEXT_PRIMARY)


try:
    from kivy.factory import Factory

    Factory.register("AppToolbar", cls=AppToolbar)
except Exception:
    pass
