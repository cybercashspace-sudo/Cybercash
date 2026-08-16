from __future__ import annotations

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ColorProperty, DictProperty, NumericProperty, StringProperty
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel

from components.notification_badge import NotificationBadge
from core.feedback_engine import tap_feedback


class BottomNavBar(MDCard):
    active_target = StringProperty("home")
    selected_target = StringProperty("")
    nav_variant = StringProperty("default")
    layout_scale = NumericProperty(1.0)
    text_scale = NumericProperty(1.0)
    icon_scale = NumericProperty(1.0)
    badge_counts = DictProperty({})
    remember_selection = BooleanProperty(True)
    animate_selection = BooleanProperty(True)
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
        self._item_widgets: dict[str, MDCard] = {}
        self.bind(
            active_target=self._on_active_target_changed,
            nav_variant=self._schedule_rebuild,
            layout_scale=self._schedule_rebuild,
            text_scale=self._schedule_rebuild,
            icon_scale=self._schedule_rebuild,
            bar_color=self._schedule_rebuild,
            active_color=self._schedule_rebuild,
            inactive_color=self._schedule_rebuild,
            badge_counts=self._schedule_rebuild,
        )
        Clock.schedule_once(self._restore_selection, 0)
        Clock.schedule_once(self._rebuild, 0)

    def _schedule_rebuild(self, *_args):
        Clock.schedule_once(self._rebuild, 0)

    def _items(self) -> list[dict]:
        return list(self._variants.get(self.nav_variant, self._variants["default"]))

    def _badge_count_for(self, target: str) -> int:
        try:
            return max(0, int((self.badge_counts or {}).get(target, 0) or 0))
        except Exception:
            return 0

    def _build_badge(self, target: str, layout_scale: float) -> NotificationBadge | None:
        count = self._badge_count_for(target)
        if count <= 0:
            return None
        badge = NotificationBadge(count=count)
        badge.size = (dp(18 * layout_scale), dp(18 * layout_scale))
        badge.pos_hint = {"right": 1, "top": 1}
        badge.opacity = 1
        badge.visible = True
        return badge

    def _persist_selection(self, target: str) -> None:
        if not self.remember_selection:
            return
        app = MDApp.get_running_app()
        app_state = getattr(app, "app_state", None) if app else None
        if app_state is None:
            return
        try:
            setattr(app_state, "bottom_nav_target", str(target or ""))
        except Exception:
            pass

    def _restore_selection(self, *_args) -> None:
        if not self.remember_selection:
            return
        app = MDApp.get_running_app()
        app_state = getattr(app, "app_state", None) if app else None
        if app_state is None:
            return
        target = str(getattr(app_state, "bottom_nav_target", "") or "").strip()
        if target:
            self.selected_target = target
            self.active_target = target

    def _on_active_target_changed(self, *_args):
        self.selected_target = str(self.active_target or "")
        self._persist_selection(self.active_target)
        self._schedule_rebuild()

    def _navigate(self, target: str) -> None:
        tap_feedback()
        app = MDApp.get_running_app()
        manager = getattr(app, "root", None)
        if manager is None:
            return

        if app is not None and hasattr(app, "ensure_screen"):
            try:
                if app.ensure_screen(target):
                    manager.current = target
                    self.active_target = target
                    return
            except Exception:
                pass

        if hasattr(manager, "has_screen") and manager.has_screen(target):
            manager.current = target
            self.active_target = target

    def _animate_active_item(self):
        if not self.animate_selection:
            return
        card = self._item_widgets.get(str(self.active_target or ""))
        if card is None:
            return
        try:
            Animation.cancel_all(card, "elevation")
            Animation(elevation=4, duration=0.08, transition="out_quad").start(card)
            Animation(elevation=1.5, duration=0.16, transition="out_back").start(card)
        except Exception:
            pass

    def _rebuild(self, *_args) -> None:
        self.clear_widgets()
        self._item_widgets = {}
        layout_scale = float(self.layout_scale or 1.0)
        text_scale = float(self.text_scale or 1.0)
        icon_scale = float(self.icon_scale or 1.0)

        is_dashboard = self.nav_variant == "dashboard"
        self.height = dp((112 if is_dashboard else 92) * layout_scale)
        self.radius = [dp(26 * layout_scale), dp(26 * layout_scale), 0, 0]
        self.padding = [dp(8 * layout_scale), dp(10 * layout_scale), dp(8 * layout_scale), dp(8 * layout_scale)]
        self.md_bg_color = list(self.bar_color)
        self.line_color = [0.52, 0.52, 0.56, 0.34]

        items = self._items()
        grid = GridLayout(cols=max(1, len(items)), spacing=0)

        def build_item(item: dict) -> MDBoxLayout:
            target = str(item["target"])
            is_active = target == self.active_target
            text_color = self.active_color if is_active else self.inactive_color
            container = MDBoxLayout(orientation="vertical", spacing=dp(4 * layout_scale), padding=[0, dp(4 * layout_scale), 0, 0], adaptive_height=True)

            if item.get("special"):
                card = MDCard(
                    size_hint=(None, None),
                    size=(dp(92 * layout_scale), dp(92 * layout_scale)),
                    radius=[dp(46 * layout_scale)],
                    md_bg_color=[0.05, 0.05, 0.06, 0.98],
                    line_color=self.active_color if is_active else [0.40, 0.40, 0.42, 0.55],
                    elevation=0,
                    pos_hint={"center_x": 0.5},
                    on_release=lambda _btn, item_target=target: self._navigate(item_target),
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
                        icon=item["icon"],
                        user_font_size=f"{32 * icon_scale:.1f}sp",
                        pos_hint={"center_x": 0.5, "center_y": 0.58},
                        theme_text_color="Custom",
                        text_color=self.active_color,
                        disabled=True,
                    )
                )
                badge = self._build_badge(target, layout_scale)
                if badge is not None:
                    art.add_widget(badge)
                card.add_widget(art)
                container.add_widget(card)
                container.add_widget(
                    MDLabel(
                        text=item["label"],
                        halign="center",
                        theme_text_color="Custom",
                        text_color=text_color,
                        font_size=f"{10.0 * text_scale:.1f}sp",
                        shorten=True,
                        shorten_from="right",
                    )
                )
                self._item_widgets[target] = card
                return container

            icon_bg = self.active_color if is_active else [0.18, 0.18, 0.20, 0.92]
            icon_fg = [0.08, 0.08, 0.08, 1] if is_active else text_color
            icon_wrap = MDCard(
                size_hint=(None, None),
                size=(dp(46 * layout_scale), dp(46 * layout_scale)),
                radius=[dp(14 * layout_scale)] if target == "home" else [dp(23 * layout_scale)],
                md_bg_color=icon_bg,
                line_color=[0.95, 0.74, 0.12, 0.28] if is_active else [1, 1, 1, 0.06],
                elevation=0,
                pos_hint={"center_x": 0.5},
                on_release=lambda _btn, item_target=target: self._navigate(item_target),
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

            icon_layer = FloatLayout(size_hint=(None, None), size=(dp(48 * layout_scale), dp(48 * layout_scale)))
            icon_layer.add_widget(icon_wrap)
            badge = self._build_badge(target, layout_scale)
            if badge is not None:
                icon_layer.add_widget(badge)

            container.add_widget(icon_layer)
            container.add_widget(
                MDLabel(
                    text=item["label"],
                    halign="center",
                    theme_text_color="Custom",
                    text_color=text_color,
                    font_size=f"{10.5 * text_scale:.1f}sp",
                    shorten=True,
                    shorten_from="right",
                )
            )
            self._item_widgets[target] = icon_wrap
            return container

        if is_dashboard:
            grid = GridLayout(cols=max(1, len(items)), spacing=0)
            for item in items:
                grid.add_widget(build_item(item))
            self.add_widget(grid)
            Clock.schedule_once(lambda _dt: self._animate_active_item(), 0)
            return

        for item in items:
            target = str(item["target"])
            is_active = target == self.active_target
            text_color = self.active_color if is_active else self.inactive_color
            container = MDBoxLayout(orientation="vertical", spacing=0, adaptive_height=True)
            icon_wrap = MDCard(
                size_hint=(None, None),
                size=(dp(46 * layout_scale), dp(46 * layout_scale)),
                radius=[dp(14 * layout_scale)] if target == "home" else [dp(23 * layout_scale)],
                md_bg_color=self.active_color if is_active else [0.18, 0.18, 0.20, 0.92],
                line_color=[0.95, 0.74, 0.12, 0.28] if is_active else [1, 1, 1, 0.06],
                elevation=0,
                pos_hint={"center_x": 0.5},
                on_release=lambda _btn, item_target=target: self._navigate(item_target),
            )
            icon_wrap.add_widget(
                MDIconButton(
                    icon=item["icon"],
                    user_font_size=f"{27 * icon_scale:.1f}sp",
                    pos_hint={"center_x": 0.5, "center_y": 0.5},
                    theme_text_color="Custom",
                    text_color=[0.08, 0.08, 0.08, 1] if is_active else text_color,
                    disabled=True,
                )
            )
            icon_layer = FloatLayout(size_hint=(None, None), size=(dp(48 * layout_scale), dp(48 * layout_scale)))
            icon_layer.add_widget(icon_wrap)
            badge = self._build_badge(target, layout_scale)
            if badge is not None:
                icon_layer.add_widget(badge)
            container.add_widget(icon_layer)
            container.add_widget(
                MDLabel(
                    text=item["label"],
                    halign="center",
                    theme_text_color="Custom",
                    text_color=text_color,
                    font_size=f"{10.5 * text_scale:.1f}sp",
                    shorten=True,
                    shorten_from="right",
                )
            )
            grid.add_widget(container)
            self._item_widgets[target] = icon_wrap

        self.add_widget(grid)
        Clock.schedule_once(lambda _dt: self._animate_active_item(), 0)


try:
    from kivy.factory import Factory

    Factory.register("BottomNavBar", cls=BottomNavBar)
except Exception:
    pass
