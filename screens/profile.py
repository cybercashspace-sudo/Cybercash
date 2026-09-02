from __future__ import annotations

from threading import Thread

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import BooleanProperty, StringProperty
from kivymd.app import MDApp

from features.auth.animations import AuthAnimations
from core.navigation import navigate
from core.screen_actions import ActionScreen
from core.refresh_mixin import RefreshableScreenMixin


Builder.load_string(
    """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp
#:import theme theme
#:import GlassCard widgets.GlassCard
#:import AppButton components.app_button.AppButton
#:import RefreshIndicator components.refresh_indicator.RefreshIndicator

<ProfileScreen>:
    MDFloatLayout:
        canvas.before:
            Color:
                rgba: theme.BACKGROUND
            Rectangle:
                pos: self.pos
                size: self.size

        ScrollView:
            do_scroll_x: False
            bar_width: 0

            MDBoxLayout:
                orientation: "vertical"
                size_hint_y: None
                height: self.minimum_height
                padding: dp(20), dp(24), dp(20), dp(28)
                spacing: dp(16)

                MDBoxLayout:
                    id: title_block
                    orientation: "horizontal"
                    adaptive_height: True
                    spacing: dp(12)

                    MDBoxLayout:
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: dp(4)

                        MDLabel:
                            text: "Profile"
                            font_size: "28sp"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: theme.TEXT_PRIMARY

                        MDLabel:
                            text: "Identity, wallet, and account summary"
                            theme_text_color: "Hint"

                    Widget:

                    AppButton:
                        id: refresh_button
                        text: "Refresh"
                        variant: "secondary"
                        size_hint_x: None
                        width: dp(140)
                        height: dp(46)
                        on_release: root.refresh_profile()

                RefreshIndicator:
                    id: refresh_indicator
                    active: root.loading
                    text: "Refreshing profile..."
                    show_text: True
                    size_hint_y: None
                    height: dp(24) if root.loading else 0
                    opacity: 1 if root.loading else 0
                    disabled: not root.loading

                MDLabel:
                    text: root.feedback_text
                    theme_text_color: "Custom"
                    text_color: root.feedback_color
                    font_size: "12sp"
                    shorten: True

                GlassCard:
                    id: hero_card
                    orientation: "horizontal"
                    adaptive_height: True
                    padding: dp(16)
                    spacing: dp(14)

                    FitImage:
                        source: root.avatar_source
                        size_hint: None, None
                        size: dp(88), dp(88)
                        radius: [dp(44)]

                    MDBoxLayout:
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: dp(4)

                        MDLabel:
                            text: root.display_name
                            font_size: "22sp"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: theme.TEXT_PRIMARY

                        MDLabel:
                            text: root.email_text
                            theme_text_color: "Hint"
                            font_size: "13sp"

                        MDLabel:
                            text: root.account_status_text
                            theme_text_color: "Custom"
                            text_color: theme.PRIMARY_LIGHT
                            font_size: "12sp"

                MDGridLayout:
                    cols: 2
                    adaptive_height: True
                    spacing: dp(12)

                    GlassCard:
                        orientation: "vertical"
                        adaptive_height: True
                        padding: dp(14)
                        spacing: dp(4)

                        MDLabel:
                            text: "Wallet Balance"
                            theme_text_color: "Hint"
                            font_size: "12sp"

                        MDLabel:
                            text: root.wallet_balance_text
                            font_size: "22sp"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: theme.PRIMARY_LIGHT

                    GlassCard:
                        orientation: "vertical"
                        adaptive_height: True
                        padding: dp(14)
                        spacing: dp(4)

                        MDLabel:
                            text: "Unread Alerts"
                            theme_text_color: "Hint"
                            font_size: "12sp"

                        MDLabel:
                            text: root.notification_count_text
                            font_size: "22sp"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: theme.TEXT_PRIMARY

                GlassCard:
                    id: details_card
                    orientation: "vertical"
                    adaptive_height: True
                    padding: dp(16)
                    spacing: dp(10)

                    MDLabel:
                        text: "Account Details"
                        font_size: "18sp"
                        bold: True
                        theme_text_color: "Custom"
                        text_color: theme.TEXT_PRIMARY

                    MDBoxLayout:
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: dp(8)

                        MDLabel:
                            text: "Phone"
                            theme_text_color: "Hint"
                            font_size: "12sp"
                        MDLabel:
                            text: root.phone_text
                            theme_text_color: "Custom"
                            text_color: theme.TEXT_PRIMARY

                        MDLabel:
                            text: "Role"
                            theme_text_color: "Hint"
                            font_size: "12sp"
                        MDLabel:
                            text: root.role_text
                            theme_text_color: "Custom"
                            text_color: theme.TEXT_PRIMARY

                        MDLabel:
                            text: "Last Sync"
                            theme_text_color: "Hint"
                            font_size: "12sp"
                        MDLabel:
                            text: root.last_sync_text
                            theme_text_color: "Custom"
                            text_color: theme.TEXT_PRIMARY

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(50)
                    spacing: dp(10)

                    AppButton:
                        text: "Back"
                        variant: "ghost"
                        on_release: root.go_back()

                    AppButton:
                        text: "Notifications"
                        variant: "secondary"
                        on_release: root.open_notifications()

                    AppButton:
                        text: "Settings"
                        variant: "secondary"
                        on_release: root.open_settings()
"""
)


class ProfileScreen(RefreshableScreenMixin, ActionScreen):
    loading = BooleanProperty(False)
    display_name = StringProperty("Your Profile")
    email_text = StringProperty("No email available")
    phone_text = StringProperty("No phone number available")
    role_text = StringProperty("User")
    account_status_text = StringProperty("Account ready")
    wallet_balance_text = StringProperty("GH₵ 0.00")
    notification_count_text = StringProperty("0 unread notifications")
    avatar_source = StringProperty("assets/profile.png")
    last_sync_text = StringProperty("Not synced yet")

    def on_pre_enter(self):
        self.sync_from_state()

    def on_enter(self):
        Clock.schedule_once(self._start_animations, 0.08)
        self.refresh_profile()

    def _start_animations(self, *_args):
        AuthAnimations.enter(self.ids.get("title_block"), 0.00, 0.35)
        AuthAnimations.slide(self.ids.get("hero_card"), 0.08, 20, 0.40)
        AuthAnimations.slide(self.ids.get("details_card"), 0.16, 24, 0.40)

    def sync_from_state(self):
        app = MDApp.get_running_app()
        state = getattr(app, "app_state", None)
        user = getattr(state, "user", None) or {}
        wallet = getattr(state, "wallet", None) or {}
        notifications = getattr(state, "notifications", []) or []
        unread = int(getattr(state, "unread_notifications", 0) or 0)

        self.display_name = str(
            user.get("full_name")
            or user.get("name")
            or user.get("first_name")
            or getattr(app, "user_name", "")
            or "Your Profile"
        ).strip()
        self.email_text = str(
            user.get("email")
            or getattr(app, "user_email", "")
            or "No email available"
        ).strip()
        self.phone_text = str(
            user.get("phone")
            or user.get("phone_number")
            or user.get("msisdn")
            or "No phone number available"
        ).strip()
        self.role_text = str(
            user.get("role")
            or ("Admin" if bool(user.get("is_admin")) else "User")
        ).strip().title()
        self.account_status_text = "Verified account" if bool(user.get("is_verified") or user.get("verified")) else "Account ready"
        self.wallet_balance_text = self._format_currency(
            wallet.get("balance") if isinstance(wallet, dict) else getattr(wallet, "balance", 0)
        )
        self.notification_count_text = f"{unread} unread notifications"
        self.avatar_source = str(user.get("avatar") or user.get("photo_url") or "assets/profile.png")
        self.last_sync_text = "Synced from dashboard cache"
        if notifications:
            self.last_sync_text = f"{len(notifications)} notifications loaded"

    def refresh_profile(self):
        if self.loading:
            return
        self._begin_refresh("Refreshing profile...")
        Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self):
        user_result = self._request("GET", "/auth/me")
        wallet_result = self._request("GET", "/wallet/me")
        Clock.schedule_once(lambda _dt: self._apply_refresh_results(user_result, wallet_result))

    def _apply_refresh_results(self, user_result, wallet_result):
        user_ok, user_payload = user_result
        wallet_ok, wallet_payload = wallet_result

        app = MDApp.get_running_app()
        if user_ok and isinstance(user_payload, dict):
            if app is not None and hasattr(app, "app_state"):
                try:
                    app.app_state.set_user(user_payload)
                except Exception:
                    pass
            if hasattr(app, "user_name"):
                app.user_name = str(user_payload.get("full_name") or user_payload.get("name") or app.user_name or "").strip()
            if hasattr(app, "user_email"):
                app.user_email = str(user_payload.get("email") or app.user_email or "").strip()

        if wallet_ok and isinstance(wallet_payload, dict):
            if app is not None and hasattr(app, "app_state"):
                try:
                    app.app_state.set_wallet(wallet_payload)
                except Exception:
                    pass

        self.sync_from_state()

        if user_ok or wallet_ok:
            self._set_feedback("Profile refreshed.", "success")
            self._complete_refresh("Profile refreshed.")
        else:
            self._set_feedback("Unable to refresh profile right now.", "warning")
            self._fail_refresh("Unable to refresh profile right now.")

    @staticmethod
    def _format_currency(value) -> str:
        try:
            amount = float(value or 0)
        except (TypeError, ValueError):
            return str(value or "GH₵ 0.00")
        return f"GH₵ {amount:,.2f}"

    def open_notifications(self):
        self._go_to_screen("notifications")

    def open_settings(self):
        self._go_to_screen("settings")

    def _go_to_screen(self, screen_name: str):
        app = MDApp.get_running_app()
        if app is not None and hasattr(app, "go_to_screen"):
            app.go_to_screen(screen_name, fallback="settings", transition_style="slide_left")
            return
        if self.manager is not None and self.manager.has_screen(screen_name):
            navigate(self.manager, screen_name, fallback="settings", transition_style="slide_left")
