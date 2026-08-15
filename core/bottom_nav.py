from __future__ import annotations

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import ColorProperty, NumericProperty, StringProperty
from kivy.uix.floatlayout import FloatLayout
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
            {"target": "virtual_card", "icon": "credit-card-outline", "label": "Cards"},
            {"target": "escrow", "icon": "shield-lock-outline", "label": "Escrow"},
            {"target": "settings", "icon": "menu", "label": "Menu"},
        ],
        "dashboard": [
            {"target": "home", "icon": "home", "label": "Home"},
            {"target": "wallet", "icon": "wallet-outline", "label": "Wallet"},
            {"target": "pay_bills", "icon": "qrcode-scan", "label": "Scan & Pay", "special": True},
            {"target": "virtual_card", "icon": "credit-card-outline", "label": "Cards"},
            {"target": "settings", "icon": "account-circle-outline", "label": "Profile"},
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
            {"target": "virtual_card", "icon": "credit-card-outline", "label": "Cards"},
            {"target": "settings", "icon": "menu", "label": "Menu"},
        ],
        "btc": [
            {"target": "home", "icon": "home", "label": "Home"},
            {"target": "virtual_card", "icon": "credit-card-outline", "label": "Cards"},
            {"target": "btc", "icon": "bitcoin", "label": "BTC"},
            {"target": "settings", "icon": "menu", "label": "Menu"},
        ],
        "agent": [
            {"target": "home", "icon": "home", "label": "Home"},
            {"target": "virtual_card", "icon": "credit-card-outline", "label": "Cards"},
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
        if app is not None and hasattr(app, "go_to_screen"):
            app.go_to_screen(target, fallback=getattr(getattr(app, "root", None), "current", "home") or "home")
            return
        manager = getattr(app, "root", None)
        if manager and hasattr(manager, "has_screen") and manager.has_screen(target):
            manager.current = target

    def _rebuild(self, *_args) -> None:
        self.clear_widgets()
        layout_scale = float(self.layout_scale or 1.0)
        text_scale = float(self.text_scale or 1.0)
        icon_scale = float(self.icon_scale or 1.0)

        is_dashboard = self.nav_variant == "dashboard"
        self.height = dp((112 if is_dashboard else 92) * layout_scale)
        self.radius = [dp(26 * layout_scale), dp(26 * layout_scale), 0, 0]
        self.padding = [dp(8 * layout_scale), dp(10 * layout_scale), dp(8 * layout_scale), dp(8 * layout_scale)]
        self.md_bg_color = list(self.bar_color)
        self.line_color = [0.52, 0.52, 0.56, 0.34]
        self.md_bg_color = list(self.bar_color)

        items = self._items()
        grid = GridLayout(cols=max(1, len(items)), spacing=0)

        def build_item(item: dict) -> MDBoxLayout:
            is_active = item["target"] == self.active_target
            text_color = self.active_color if is_active else self.inactive_color
            container = MDBoxLayout(orientation="vertical", spacing=dp(4 * layout_scale), padding=[0, dp(4 * layout_scale), 0, 0])

            if item.get("special"):
                card = MDCard(
                    size_hint=(None, None),
                    size=(dp(92 * layout_scale), dp(92 * layout_scale)),
                    radius=[dp(46 * layout_scale)],
                    md_bg_color=[0.05, 0.05, 0.06, 0.98],
                    line_color=self.active_color if is_active else [0.40, 0.40, 0.42, 0.55],
                    elevation=0,
                    pos_hint={"center_x": 0.5},
                    on_release=lambda _btn, target=item["target"]: self._navigate(target),
                )
                art = FloatLayout()
                art.add_widget(
                    MDCard(
                        size_hint=(None, None),
                        size=(dp(68 * layout_scale), dp(68 * layout_scale)),
                        radius=[dp(34 * layout_scale)],
                        md_bg_color=[0.08, 0.08, 0.09, 0.98],
                        line_color=[0.95, 0.74, 0.12, 0.88],
                        elevation=0,
                        pos_hint={"center_x": 0.5, "center_y": 0.58},
                    )
                )
                art.add_widget(
                    MDIconButton(
                        icon="qrcode-scan",
                        user_font_size=f"{32 * icon_scale:.1f}sp",
                        pos_hint={"center_x": 0.5, "center_y": 0.58},
                        theme_text_color="Custom",
                        text_color=self.active_color,
                        disabled=True,
                    )
                )
                card.add_widget(art)
                container.add_widget(card)
                container.add_widget(
                    MDLabel(
                        text=item["label"],
                        halign="center",
                        theme_text_color="Custom",
                        text_color=text_color,
                        font_size=f"{10.0 * text_scale:.1f}sp",
                    )
                )
                return container

            icon_bg = self.active_color if is_active else [0.18, 0.18, 0.20, 0.92]
            icon_fg = [0.08, 0.08, 0.08, 1] if is_active else text_color
            icon_wrap = MDCard(
                size_hint=(None, None),
                size=(dp(46 * layout_scale), dp(46 * layout_scale)),
                radius=[dp(14 * layout_scale)] if item["target"] == "home" else [dp(23 * layout_scale)],
                md_bg_color=icon_bg,
                line_color=[0.95, 0.74, 0.12, 0.28] if is_active else [1, 1, 1, 0.06],
                elevation=0,
                pos_hint={"center_x": 0.5},
                on_release=lambda _btn, target=item["target"]: self._navigate(target),
            )
            icon_wrap.add_widget(
                MDIconButton(
                    icon=item["icon"],
                    user_font_size=f"{23 * icon_scale:.1f}sp",
                    pos_hint={"center_x": 0.5, "center_y": 0.5},
                    theme_text_color="Custom",
                    text_color=icon_fg,
                    disabled=True,
                )
            )
            container.add_widget(icon_wrap)
            container.add_widget(
                MDLabel(
                    text=item["label"],
                    halign="center",
                    theme_text_color="Custom",
                    text_color=text_color,
                    font_size=f"{10.5 * text_scale:.1f}sp",
                )
            )
            return container

        if is_dashboard:
            grid = GridLayout(cols=max(1, len(items)), spacing=0)
            for item in items:
                grid.add_widget(build_item(item))
            self.add_widget(grid)
            return

        for item in items:
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
