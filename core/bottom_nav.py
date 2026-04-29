from __future__ import annotations

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import ColorProperty, NumericProperty, StringProperty
from kivy.uix.gridlayout import GridLayout
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel

from core.feedback_engine import tap_feedback


class BottomNavBar(MDCard):
    active_target = StringProperty("home")
    nav_variant = StringProperty("default")
    layout_scale = NumericProperty(1.0)
    text_scale = NumericProperty(1.0)
    icon_scale = NumericProperty(1.0)
    bar_color = ColorProperty([0.12, 0.14, 0.18, 0.95])
    active_color = ColorProperty([0.94, 0.79, 0.46, 1.0])
    inactive_color = ColorProperty([0.95, 0.95, 0.95, 1.0])

    _variants = {
        "default": [
            {"target": "home", "icon": "home", "label": "Home"},
            {"target": "cards", "icon": "credit-card-outline", "label": "Cards"},
            {"target": "escrow", "icon": "shield-lock-outline", "label": "Escrow"},
            {"target": "settings", "icon": "menu", "label": "Menu"},
        ],
        "admin": [
            {"target": "admin_dashboard", "icon": "home", "label": "Home"},
            {"target": "admin_revenue", "icon": "chart-line", "label": "Revenue"},
            {"target": "admin_withdrawals", "icon": "cash-refund", "label": "Withdraw"},
            {"target": "settings", "icon": "cog-outline", "label": "Settings"},
        ],
        "send": [
            {"target": "home", "icon": "home", "label": "Home"},
            {"target": "p2p_transfer", "icon": "send", "label": "Send"},
            {"target": "cards", "icon": "credit-card-outline", "label": "Cards"},
            {"target": "settings", "icon": "menu", "label": "Menu"},
        ],
        "btc": [
            {"target": "home", "icon": "home", "label": "Home"},
            {"target": "cards", "icon": "credit-card-outline", "label": "Cards"},
            {"target": "btc", "icon": "bitcoin", "label": "BTC"},
            {"target": "settings", "icon": "menu", "label": "Menu"},
        ],
        "agent": [
            {"target": "home", "icon": "home", "label": "Home"},
            {"target": "cards", "icon": "credit-card-outline", "label": "Cards"},
            {"target": "escrow", "icon": "shield-lock-outline", "label": "Escrow"},
            {"target": "agent", "icon": "menu", "label": "Menu"},
        ],
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.elevation = 1
        self.bind(
            active_target=self._schedule_rebuild,
            nav_variant=self._schedule_rebuild,
            layout_scale=self._schedule_rebuild,
            text_scale=self._schedule_rebuild,
            icon_scale=self._schedule_rebuild,
            bar_color=self._schedule_rebuild,
            active_color=self._schedule_rebuild,
            inactive_color=self._schedule_rebuild,
        )
        Clock.schedule_once(self._rebuild, 0)

    def _schedule_rebuild(self, *_args):
        Clock.schedule_once(self._rebuild, 0)

    def _items(self) -> list[dict]:
        return list(self._variants.get(self.nav_variant, self._variants["default"]))

    def _navigate(self, target: str) -> None:
        tap_feedback()
        app = MDApp.get_running_app()
        manager = getattr(app, "root", None)
        if manager and hasattr(manager, "has_screen") and manager.has_screen(target):
            manager.current = target

    def _rebuild(self, *_args) -> None:
        self.clear_widgets()
        layout_scale = float(self.layout_scale or 1.0)
        text_scale = float(self.text_scale or 1.0)
        icon_scale = float(self.icon_scale or 1.0)

        self.height = dp(92 * layout_scale)
        self.radius = [dp(24 * layout_scale), dp(24 * layout_scale), 0, 0]
        self.padding = [dp(8 * layout_scale)] * 4
        self.md_bg_color = list(self.bar_color)

        grid = GridLayout(cols=4, spacing=0)
        for item in self._items():
            is_active = item["target"] == self.active_target
            text_color = self.active_color if is_active else self.inactive_color

            container = MDBoxLayout(orientation="vertical", spacing=0)
            container.add_widget(
                MDIconButton(
                    icon=item["icon"],
                    user_font_size=f"{27 * icon_scale:.1f}sp",
                    pos_hint={"center_x": 0.5},
                    theme_text_color="Custom",
                    text_color=text_color,
                    on_release=lambda _btn, target=item["target"]: self._navigate(target),
                )
            )
            container.add_widget(
                MDLabel(
                    text=item["label"],
                    halign="center",
                    theme_text_color="Custom",
                    text_color=text_color,
                    font_size=f"{10.5 * text_scale:.1f}sp",
                )
            )
            grid.add_widget(container)

        self.add_widget(grid)
