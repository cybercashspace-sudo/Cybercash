from __future__ import annotations

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ColorProperty, DictProperty, NumericProperty, StringProperty
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.screenmanager import Screen
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel

from components.notification_badge import NotificationBadge
from core.feedback_engine import tap_feedback
from core.navigation import navigate


class _BottomNavItem(ButtonBehavior, MDBoxLayout):
    """Make both the nav icon and its label part of one large tap target."""


class BottomNavBar(MDCard):
    active_target = StringProperty("")
    selected_target = StringProperty("")
    nav_variant = StringProperty("default")
    layout_scale = NumericProperty(1.0)
    text_scale = NumericProperty(1.0)
    icon_scale = NumericProperty(1.0)
    badge_counts = DictProperty({})
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
            {"target": "pay_bills", "icon": "qrcode-scan", "label": "Scan & Pay"},
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
        self._rebuild_event = None
        self._screen_manager = None
        self._host_screen = None
        self.bind(
            active_target=self._on_active_target_changed,
            nav_variant=self._on_nav_variant_changed,
            layout_scale=self._schedule_rebuild,
            text_scale=self._schedule_rebuild,
            icon_scale=self._schedule_rebuild,
            bar_color=self._schedule_rebuild,
            active_color=self._schedule_rebuild,
            inactive_color=self._schedule_rebuild,
            badge_counts=self._schedule_rebuild,
        )
        Clock.schedule_once(self._rebuild, 0)

    def on_parent(self, _instance, parent):
        if parent is None:
            self._unbind_screen_manager()
            return
        Clock.schedule_once(self._bind_screen_manager, 0)

    def _schedule_rebuild(self, *_args):
        event = getattr(self, "_rebuild_event", None)
        if event is not None:
            try:
                event.cancel()
            except Exception:
                pass
        self._rebuild_event = Clock.schedule_once(self._rebuild, 0)

    def _on_nav_variant_changed(self, *_args) -> None:
        self._schedule_rebuild()
        self._sync_selection_to_current_screen()

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

    def _find_host_screen(self):
        parent = self.parent
        while parent is not None:
            if isinstance(parent, Screen):
                return parent
            parent = getattr(parent, "parent", None)
        return None

    def _unbind_screen_manager(self) -> None:
        manager = self._screen_manager
        if manager is not None:
            try:
                manager.unbind(current=self._on_screen_manager_current)
            except Exception:
                pass
        host_screen = self._host_screen
        if host_screen is not None:
            try:
                host_screen.unbind(manager=self._on_host_screen_manager_changed)
            except Exception:
                pass
        self._screen_manager = None
        self._host_screen = None

    def _on_host_screen_manager_changed(self, *_args) -> None:
        self._bind_screen_manager()

    def _bind_screen_manager(self, *_args) -> None:
        host_screen = self._find_host_screen()
        if host_screen is not self._host_screen:
            self._unbind_screen_manager()
            if host_screen is not None:
                self._host_screen = host_screen
                host_screen.bind(manager=self._on_host_screen_manager_changed)
        manager = getattr(host_screen, "manager", None) if host_screen is not None else None
        if manager is None:
            if self._screen_manager is not None:
                try:
                    self._screen_manager.unbind(current=self._on_screen_manager_current)
                except Exception:
                    pass
                self._screen_manager = None
            return
        if manager is not self._screen_manager:
            if self._screen_manager is not None:
                try:
                    self._screen_manager.unbind(current=self._on_screen_manager_current)
                except Exception:
                    pass
            self._screen_manager = manager
            manager.bind(current=self._on_screen_manager_current)
        self._sync_selection_to_current_screen()

    def _on_screen_manager_current(self, *_args) -> None:
        self._sync_selection_to_current_screen()

    def _sync_selection_to_current_screen(self) -> None:
        manager = self._screen_manager
        host_screen = self._host_screen
        if manager is None or host_screen is None:
            return
        if str(getattr(manager, "current", "") or "") != str(getattr(host_screen, "name", "") or ""):
            return

        visible_targets = {str(item.get("target", "")) for item in self._items()}
        route = str(getattr(manager, "current", "") or "").strip()
        configured = str(self.active_target or "").strip()
        if route in visible_targets:
            target = route
        elif configured in visible_targets:
            target = configured
        else:
            target = ""
        if self.active_target != target:
            self.active_target = target
        elif self.selected_target != target:
            self.selected_target = target

    def _on_active_target_changed(self, *_args):
        self.selected_target = str(self.active_target or "")
        self._schedule_rebuild()

    def _navigate(self, target: str) -> None:
        target = str(target or "").strip()
        if not target:
            return
        app = MDApp.get_running_app()
        manager = getattr(app, "root", None)
        if manager is None:
            return

        current = str(getattr(manager, "current", "") or "").strip()
        if current == target:
            self._sync_selection_to_current_screen()
            return
        tap_feedback()

        if app is not None and hasattr(app, "go_to_screen"):
            try:
                if app.go_to_screen(
                    target,
                    fallback=str(getattr(manager, "current", "home") or "home"),
                    transition_style="fade",
                ):
                    self._sync_selection_to_current_screen()
                    return
            except Exception:
                pass
            return

        if hasattr(manager, "has_screen") and manager.has_screen(target):
            if navigate(
                manager,
                target,
                previous=str(getattr(manager, "current", "home") or "home"),
                fallback=str(getattr(manager, "current", "home") or "home"),
                transition_style="fade",
            ):
                self._sync_selection_to_current_screen()

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
        self._rebuild_event = None
        self.clear_widgets()
        self._item_widgets = {}
        layout_scale = float(self.layout_scale or 1.0)
        text_scale = float(self.text_scale or 1.0)
        icon_scale = float(self.icon_scale or 1.0)

        # Match the compact APK Escrow navigation on every screen. Each variant
        # still keeps its own destinations, labels, and active route.
        self.height = dp(92 * layout_scale)
        self.radius = [dp(26 * layout_scale), dp(26 * layout_scale), 0, 0]
        self.padding = [dp(8 * layout_scale), dp(10 * layout_scale), dp(8 * layout_scale), dp(8 * layout_scale)]
        self.md_bg_color = list(self.bar_color)
        self.line_color = [0.52, 0.52, 0.56, 0.34]

        items = self._items()
        icon_slot_height = dp(48 * layout_scale)
        grid = GridLayout(cols=max(1, len(items)), rows=1, spacing=0, size_hint=(1, 1))

        def build_item(item: dict) -> MDBoxLayout:
            target = str(item["target"])
            is_active = target == self.active_target
            text_color = self.active_color if is_active else self.inactive_color
            container = _BottomNavItem(
                orientation="vertical",
                size_hint=(1, 1),
                spacing=dp(2 * layout_scale),
                padding=0,
                on_release=lambda _item, item_target=target: self._navigate(item_target),
            )
            icon_wrap = MDCard(
                size_hint=(None, None),
                size=(dp(46 * layout_scale), dp(46 * layout_scale)),
                radius=[dp(14 * layout_scale)] if target == "home" else [dp(23 * layout_scale)],
                md_bg_color=self.active_color if is_active else [0.18, 0.18, 0.20, 0.92],
                line_color=[0.95, 0.74, 0.12, 0.28] if is_active else [1, 1, 1, 0.06],
                elevation=0,
                pos_hint={"center_x": 0.5, "center_y": 0.5},
            )
            icon_button = MDIconButton(
                icon=item["icon"],
                icon_size=f"{25 * icon_scale:.1f}sp",
                theme_text_color="Custom",
                text_color=[0.08, 0.08, 0.08, 1] if is_active else text_color,
                disabled=True,
            )
            icon_wrap.add_widget(icon_button)

            def center_icon(card, *_args, button=icon_button):
                button.pos = (
                    card.center_x - button.width / 2,
                    card.center_y - button.height / 2,
                )

            icon_wrap.bind(pos=center_icon, size=center_icon)
            center_icon(icon_wrap)
            badge = self._build_badge(target, layout_scale)

            icon_layer = FloatLayout(size_hint=(1, None), height=icon_slot_height)
            icon_layer.add_widget(icon_wrap)
            if badge is not None:
                icon_layer.add_widget(badge)
            container.add_widget(icon_layer)
            container.add_widget(
                MDLabel(
                    text=item["label"],
                    size_hint=(1, None),
                    height=dp(18 * layout_scale),
                    halign="center",
                    valign="middle",
                    theme_text_color="Custom",
                    text_color=text_color,
                    font_size=f"{10.5 * text_scale:.1f}sp",
                    shorten=True,
                    shorten_from="right",
                    text_size=(None, dp(18 * layout_scale)),
                )
            )
            self._item_widgets[target] = icon_wrap
            return container

        for item in items:
            grid.add_widget(build_item(item))

        self.add_widget(grid)
        Clock.schedule_once(lambda _dt: self._animate_active_item(), 0)

try:
    from kivy.factory import Factory

    Factory.register("BottomNavBar", cls=BottomNavBar)
except Exception:
    pass
