from __future__ import annotations

import threading

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import BooleanProperty, StringProperty
from kivymd.app import MDApp

from api.auth import logout
from api.client import API_URL, api_client
from core.bottom_nav import BottomNavBar
from core.popup_manager import show_confirm_dialog, show_message_dialog
from core.screen_actions import ActionScreen
from storage import save_token


KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp
#:set BG (0.043, 0.059, 0.078, 1)
#:set CARD (0.075, 0.096, 0.126, 0.96)
#:set CARD2 (0.085, 0.114, 0.142, 0.96)
#:set GOLD (0.831, 0.686, 0.216, 1)
#:set GREEN (0.122, 0.239, 0.169, 1)
#:set TEXT_MAIN (0.96, 0.97, 0.98, 1)
#:set TEXT_SUB (0.69, 0.73, 0.78, 1)

<SettingsScreen>:
    MDBoxLayout:
        orientation: "vertical"

        canvas.before:
            Color:
                rgba: app.ui_background
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
                padding: [dp(16), dp(16), dp(16), dp(96)]
                spacing: dp(12)

                MDCard:
                    radius: [dp(24)]
                    md_bg_color: app.ui_surface
                    line_color: (0.27, 0.23, 0.14, 0.45)
                    elevation: 0
                    padding: dp(18)
                    size_hint_y: None
                    height: self.minimum_height

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(10)
                        adaptive_height: True

                        MDBoxLayout:
                            orientation: "horizontal"
                            size_hint_y: None
                            height: self.minimum_height
                            spacing: dp(12)

                            MDBoxLayout:
                                orientation: "vertical"
                                spacing: dp(2)
                                adaptive_height: True

                                MDLabel:
                                    text: "Settings"
                                    font_style: "Title"
                                    bold: True
                                    theme_text_color: "Custom"
                                    text_color: app.gold
                                    adaptive_height: True

                                MDLabel:
                                    text: "Manage security, payments, alerts, and account preferences in one place."
                                    theme_text_color: "Custom"
                                    text_color: app.ui_text_secondary
                                    font_size: sp(12)
                                    adaptive_height: True

                            MDLabel:
                                text: root.role_badge
                                size_hint_x: None
                                width: dp(110)
                                halign: "right"
                                valign: "middle"
                                text_size: self.size
                                bold: True
                                theme_text_color: "Custom"
                                text_color: app.gold
                                adaptive_height: True

                        MDLabel:
                            text: root.feedback_text
                            theme_text_color: "Custom"
                            text_color: root.feedback_color
                            font_size: sp(12)
                            adaptive_height: True

                        MDRaisedButton:
                            text: "Save Changes"
                            md_bg_color: app.gold
                            text_color: app.ui_background
                            size_hint_y: None
                            height: dp(46)
                            on_release: root.save_settings()

                        MDRaisedButton:
                            text: "Toggle Theme"
                            md_bg_color: app.ui_surface_soft
                            text_color: app.ui_text_primary
                            size_hint_y: None
                            height: dp(46)
                            on_release: app.toggle_theme()

                MDCard:
                    radius: [dp(22)]
                    md_bg_color: app.ui_surface_soft
                    line_color: (0.27, 0.23, 0.14, 0.45)
                    elevation: 0
                    padding: dp(16)
                    size_hint_y: None
                    height: self.minimum_height

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(10)
                        adaptive_height: True

                        MDLabel:
                            text: "Security"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: app.gold
                            font_size: sp(18)
                            adaptive_height: True

                        MDLabel:
                            text: "Protect sign-in, approvals, and withdrawal access."
                            theme_text_color: "Custom"
                            text_color: app.ui_text_secondary
                            font_size: sp(12)
                            adaptive_height: True

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(42)
                            MDLabel:
                                text: "Enable biometric login"
                                theme_text_color: "Custom"
                                text_color: app.ui_text_primary
                            MDSwitch:
                                id: biometric_switch

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(42)
                            MDLabel:
                                text: "Require OTP verification"
                                theme_text_color: "Custom"
                                text_color: app.ui_text_primary
                            MDSwitch:
                                id: otp_switch

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(42)
                            MDLabel:
                                text: "Protect withdrawals with a transaction PIN"
                                theme_text_color: "Custom"
                                text_color: app.ui_text_primary
                            MDSwitch:
                                id: transaction_pin_switch

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(42)
                            MDLabel:
                                text: "Bind this device to your account"
                                theme_text_color: "Custom"
                                text_color: app.ui_text_primary
                            MDSwitch:
                                id: device_binding_switch

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(42)
                            MDLabel:
                                text: "Send login alerts"
                                theme_text_color: "Custom"
                                text_color: app.ui_text_primary
                            MDSwitch:
                                id: login_alerts_switch

                        MDTextField:
                            id: withdrawal_limit_input
                            hint_text: "Withdrawal limit (GHS)"
                            helper_text: "Applies to your account withdrawal cap."
                            helper_text_mode: "on_focus"
                            mode: "outlined"
                            input_filter: "float"
                            multiline: False

                MDCard:
                    radius: [dp(22)]
                    md_bg_color: app.ui_surface_soft
                    line_color: (0.27, 0.23, 0.14, 0.45)
                    elevation: 0
                    padding: dp(16)
                    size_hint_y: None
                    height: self.minimum_height

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(10)
                        adaptive_height: True

                        MDLabel:
                            text: "Payments"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: app.gold
                            font_size: sp(18)
                            adaptive_height: True

                        MDLabel:
                            text: "Choose how payouts behave and what fees are visible."
                            theme_text_color: "Custom"
                            text_color: app.ui_text_secondary
                            font_size: sp(12)
                            adaptive_height: True

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(42)
                            MDLabel:
                                text: "Auto-settle to MoMo"
                                theme_text_color: "Custom"
                                text_color: app.ui_text_primary
                            MDSwitch:
                                id: auto_settle_switch

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(42)
                            MDLabel:
                                text: "Show fee breakdown"
                                theme_text_color: "Custom"
                                text_color: app.ui_text_primary
                            MDSwitch:
                                id: fee_display_switch

                        MDTextField:
                            id: payout_method_input
                            hint_text: "Default payout method"
                            helper_text: "momo, bank, or crypto"
                            helper_text_mode: "on_focus"
                            mode: "outlined"
                            multiline: False

                        MDTextField:
                            id: preferred_currency_input
                            hint_text: "Preferred currency"
                            mode: "outlined"
                            multiline: False

                MDCard:
                    radius: [dp(22)]
                    md_bg_color: app.ui_surface_soft
                    line_color: (0.27, 0.23, 0.14, 0.45)
                    elevation: 0
                    padding: dp(16)
                    size_hint_y: None
                    height: self.minimum_height

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(10)
                        adaptive_height: True

                        MDLabel:
                            text: "Notifications"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: app.gold
                            font_size: sp(18)
                            adaptive_height: True

                        MDLabel:
                            text: "Decide where alerts should reach you."
                            theme_text_color: "Custom"
                            text_color: app.ui_text_secondary
                            font_size: sp(12)
                            adaptive_height: True

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(42)
                            MDLabel:
                                text: "Send SMS alerts"
                                theme_text_color: "Custom"
                                text_color: app.ui_text_primary
                            MDSwitch:
                                id: sms_alerts_switch

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(42)
                            MDLabel:
                                text: "Send email alerts"
                                theme_text_color: "Custom"
                                text_color: app.ui_text_primary
                            MDSwitch:
                                id: email_alerts_switch

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(42)
                            MDLabel:
                                text: "Enable push notifications"
                                theme_text_color: "Custom"
                                text_color: app.ui_text_primary
                            MDSwitch:
                                id: push_notifications_switch

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(42)
                            MDLabel:
                                text: "Receive fraud alerts"
                                theme_text_color: "Custom"
                                text_color: app.ui_text_primary
                            MDSwitch:
                                id: fraud_alerts_switch

                MDCard:
                    radius: [dp(22)]
                    md_bg_color: app.ui_surface_soft
                    line_color: (0.27, 0.23, 0.14, 0.45)
                    elevation: 0
                    padding: dp(16)
                    size_hint_y: None
                    height: self.minimum_height

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(10)
                        adaptive_height: True

                        MDLabel:
                            text: "Account"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: app.gold
                            font_size: sp(18)
                            adaptive_height: True

                        MDLabel:
                            text: "Keep your session secure and manage your PIN."
                            theme_text_color: "Custom"
                            text_color: app.ui_text_secondary
                            font_size: sp(12)
                            adaptive_height: True

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(46)
                            spacing: dp(10)

                            MDRaisedButton:
                                text: "Change PIN"
                                md_bg_color: app.emerald
                                size_hint_x: 0.5
                                on_release: root.open_change_pin_help()

                            MDRaisedButton:
                                text: "Sign out"
                                md_bg_color: (0.27, 0.18, 0.18, 1)
                                size_hint_x: 0.5
                                on_release: root.confirm_logout()

                MDCard:
                    id: admin_card
                    radius: [dp(22)]
                    md_bg_color: app.ui_surface_soft
                    line_color: (0.27, 0.23, 0.14, 0.45)
                    elevation: 0
                    padding: dp(16)
                    size_hint_y: None
                    height: self.minimum_height

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(10)
                        adaptive_height: True

                        MDLabel:
                            text: "Admin Platform Controls"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: app.gold
                            font_size: sp(18)
                            adaptive_height: True

                        MDLabel:
                            text: "These controls apply platform-wide."
                            theme_text_color: "Custom"
                            text_color: app.ui_text_secondary
                            font_size: sp(12)
                            adaptive_height: True

                        MDLabel:
                            text: "Manage fees, thresholds, and commission defaults."
                            theme_text_color: "Custom"
                            text_color: app.ui_text_secondary
                            font_size: sp(12)
                            adaptive_height: True

                        MDTextField:
                            id: admin_registration_fee_input
                            hint_text: "API / agent activation fee (GHS)"
                            helper_text: "Used when agents activate."
                            helper_text_mode: "on_focus"
                            mode: "outlined"
                            input_filter: "float"
                            multiline: False

                        MDTextField:
                            id: platform_fee_rate_input
                            hint_text: "Platform fee rate"
                            helper_text: "Decimal rate, e.g. 0.01 = 1%"
                            helper_text_mode: "on_focus"
                            mode: "outlined"
                            input_filter: "float"
                            multiline: False

                        MDTextField:
                            id: admin_withdrawal_limit_input
                            hint_text: "Platform withdrawal limit (GHS)"
                            helper_text: "Maximum platform withdrawal."
                            helper_text_mode: "on_focus"
                            mode: "outlined"
                            input_filter: "float"
                            multiline: False

                        MDTextField:
                            id: fraud_threshold_input
                            hint_text: "Fraud threshold (GHS)"
                            helper_text: "Amounts above this are flagged."
                            helper_text_mode: "on_focus"
                            mode: "outlined"
                            input_filter: "float"
                            multiline: False

                        MDTextField:
                            id: commission_rate_input
                            hint_text: "Default commission rate"
                            helper_text: "Decimal rate, e.g. 0.02 = 2%"
                            helper_text_mode: "on_focus"
                            mode: "outlined"
                            input_filter: "float"
                            multiline: False

                        MDRaisedButton:
                            text: "Open Admin Dashboard"
                            md_bg_color: app.emerald
                            size_hint_y: None
                            height: dp(46)
                            on_release: root.confirm_open_admin_dashboard()

        BottomNavBar:
            nav_variant: "default"
            active_target: "settings"
            layout_scale: root.layout_scale
            text_scale: root.text_scale
            icon_scale: root.icon_scale
            bar_color: app.ui_surface
            active_color: app.gold
            inactive_color: app.ui_text_secondary
"""


class SettingsScreen(ActionScreen):
    is_admin_gate = BooleanProperty(False)
    role_badge = StringProperty("USER MODE")

    _admin_card = None
    _admin_card_parent = None
    _admin_card_parent_index = None

    def on_kv_post(self, _base_widget):
        super().on_kv_post(_base_widget)
        admin_proxy = self.ids.get("admin_card")
        self._admin_card = None
        if admin_proxy is not None:
            try:
                self._admin_card = admin_proxy.__ref__() if hasattr(admin_proxy, "__ref__") else admin_proxy
            except ReferenceError:
                self._admin_card = None
        if self._admin_card is not None:
            self._admin_card_parent = self._admin_card.parent
            if self._admin_card_parent is not None:
                try:
                    self._admin_card_parent_index = self._admin_card_parent.children.index(self._admin_card)
                except Exception:
                    self._admin_card_parent_index = None
        self.refresh_admin_gate()

    def on_pre_enter(self):
        self.refresh_admin_gate()
        self.load_settings()

    def _show_popup(self, title: str, message: str, on_close=None):
        show_message_dialog(self, title=title, message=message, close_label="Close", on_close=on_close)

    def _set_admin_card_visible(self, visible: bool) -> None:
        if self._admin_card is None or self._admin_card_parent is None:
            return
        if visible:
            if self._admin_card.parent is None:
                if self._admin_card_parent_index is None:
                    self._admin_card_parent.add_widget(self._admin_card)
                else:
                    self._admin_card_parent.add_widget(self._admin_card, index=int(self._admin_card_parent_index))
        else:
            if self._admin_card.parent is not None:
                try:
                    self._admin_card_parent.remove_widget(self._admin_card)
                except Exception:
                    pass

    def refresh_admin_gate(self) -> None:
        ok, payload = self._request("GET", "/auth/me")
        is_admin = False
        role = "user"
        if ok and isinstance(payload, dict):
            role = str(payload.get("role", "") or "").strip().lower() or "user"
            is_admin = bool(payload.get("is_admin", False)) or role == "admin"
        self.is_admin_gate = bool(is_admin)
        self.role_badge = "ADMIN MODE" if self.is_admin_gate else f"{role.upper()} MODE"
        self._set_admin_card_visible(self.is_admin_gate)

    def load_settings(self) -> None:
        if getattr(self, "_loading_settings", False):
            return
        self._loading_settings = True
        self._load_seq = int(getattr(self, "_load_seq", 0)) + 1
        seq = self._load_seq
        self._set_feedback("Loading your settings...", "info")
        threading.Thread(target=self._load_settings_worker, args=(seq,), daemon=True).start()

    def _load_settings_worker(self, seq: int) -> None:
        user_result = self._request("GET", "/settings/me")
        platform_result = (False, {})
        if self.is_admin_gate:
            platform_result = self._request("GET", "/settings/platform")
        Clock.schedule_once(lambda _dt: self._apply_loaded_settings(seq, user_result, platform_result))

    def _apply_loaded_settings(self, seq: int, user_result, platform_result) -> None:
        if seq != int(getattr(self, "_load_seq", 0)):
            return
        self._loading_settings = False

        user_ok, user_payload = user_result
        if not user_ok:
            self._set_feedback(self._extract_detail(user_payload) or "Unable to load your settings.", "error")
            return
        if isinstance(user_payload, dict):
            self._apply_user_settings(user_payload)

        if self.is_admin_gate:
            platform_ok, platform_payload = platform_result
            if not platform_ok:
                self._set_feedback(self._extract_detail(platform_payload) or "Unable to load admin settings.", "warning")
                return
            if isinstance(platform_payload, dict):
                self._apply_platform_settings(platform_payload)

        self._set_feedback("Settings ready. Make your changes and tap Save Changes.", "success")

    def _apply_user_settings(self, payload: dict) -> None:
        self._set_switch("biometric_switch", payload.get("biometric", False))
        self._set_switch("otp_switch", payload.get("otp", True))
        self._set_switch("auto_settle_switch", payload.get("auto_settle", True))
        self._set_switch("sms_alerts_switch", payload.get("sms_alerts", True))
        self._set_switch("email_alerts_switch", payload.get("email_alerts", False))
        self._set_switch("transaction_pin_switch", payload.get("transaction_pin", True))
        self._set_switch("device_binding_switch", payload.get("device_binding", True))
        self._set_switch("login_alerts_switch", payload.get("login_alerts", True))
        self._set_switch("push_notifications_switch", payload.get("push_notifications", False))
        self._set_switch("fraud_alerts_switch", payload.get("fraud_alerts", True))
        self._set_text("withdrawal_limit_input", payload.get("withdrawal_limit", 2000.0), "2000")
        self._set_text("payout_method_input", payload.get("default_payout_method", "momo"), "momo")
        self._set_text("preferred_currency_input", payload.get("preferred_currency", "GHS"), "GHS")
        self._set_switch("fee_display_switch", payload.get("fee_display", True))

    def _apply_platform_settings(self, payload: dict) -> None:
        self._set_text("admin_registration_fee_input", payload.get("agent_registration_fee", 100.0), "100")
        self._set_text("platform_fee_rate_input", payload.get("platform_fee_percentage", 0.01), "0.01")
        self._set_text("admin_withdrawal_limit_input", payload.get("withdrawal_limit", 1000.0), "1000")
        self._set_text("fraud_threshold_input", payload.get("fraud_threshold", 1000.0), "1000")
        self._set_text("commission_rate_input", payload.get("commission_rate", 0.02), "0.02")

    def _set_switch(self, name: str, value) -> None:
        widget = self.ids.get(name)
        if widget is not None:
            widget.active = bool(value)

    def _set_text(self, name: str, value, default: str = "") -> None:
        widget = self.ids.get(name)
        if widget is None:
            return
        widget.text = default if value is None else str(value)

    def _read_bool(self, name: str, default: bool = False) -> bool:
        widget = self.ids.get(name)
        return bool(getattr(widget, "active", default)) if widget is not None else bool(default)

    def _read_text(self, name: str, default: str = "") -> str:
        widget = self.ids.get(name)
        value = str(getattr(widget, "text", "") or "").strip() if widget is not None else ""
        return value or default

    def _read_float(self, name: str, default: float = 0.0) -> float:
        raw = self._read_text(name, "")
        if not raw:
            return float(default)
        try:
            return float(raw)
        except (TypeError, ValueError):
            return float(default)

    def save_settings(self) -> None:
        if getattr(self, "_saving_settings", False):
            return
        self._saving_settings = True
        self._save_seq = int(getattr(self, "_save_seq", 0)) + 1
        seq = self._save_seq

        user_payload = {
            "biometric": self._read_bool("biometric_switch"),
            "otp": self._read_bool("otp_switch"),
            "auto_settle": self._read_bool("auto_settle_switch"),
            "sms_alerts": self._read_bool("sms_alerts_switch"),
            "email_alerts": self._read_bool("email_alerts_switch"),
            "transaction_pin": self._read_bool("transaction_pin_switch"),
            "device_binding": self._read_bool("device_binding_switch"),
            "login_alerts": self._read_bool("login_alerts_switch"),
            "push_notifications": self._read_bool("push_notifications_switch"),
            "fraud_alerts": self._read_bool("fraud_alerts_switch"),
            "withdrawal_limit": self._read_float("withdrawal_limit_input", 2000.0),
            "default_payout_method": self._read_text("payout_method_input", "momo").lower(),
            "preferred_currency": self._read_text("preferred_currency_input", "GHS").upper(),
            "fee_display": self._read_bool("fee_display_switch"),
        }

        platform_payload = None
        if self.is_admin_gate:
            platform_payload = {
                "agent_registration_fee": self._read_float("admin_registration_fee_input", 100.0),
                "platform_fee_percentage": self._read_float("platform_fee_rate_input", 0.01),
                "withdrawal_limit": self._read_float("admin_withdrawal_limit_input", 1000.0),
                "fraud_threshold": self._read_float("fraud_threshold_input", 1000.0),
                "commission_rate": self._read_float("commission_rate_input", 0.02),
            }

        self._set_feedback("Saving settings...", "info")
        threading.Thread(target=self._save_settings_worker, args=(seq, user_payload, platform_payload), daemon=True).start()

    def _save_settings_worker(self, seq: int, user_payload: dict, platform_payload: dict | None) -> None:
        user_result = self._request("PUT", "/settings/me", payload=user_payload)
        platform_result = (False, {})
        if platform_payload is not None:
            platform_result = self._request("PUT", "/settings/platform", payload=platform_payload)
        Clock.schedule_once(lambda _dt: self._apply_save_results(seq, user_result, platform_result))

    def _apply_save_results(self, seq: int, user_result, platform_result) -> None:
        if seq != int(getattr(self, "_save_seq", 0)):
            return
        self._saving_settings = False

        user_ok, user_payload = user_result
        if not user_ok:
            error_message = self._extract_detail(user_payload) or "Unable to save settings."
            self._set_feedback(error_message, "error")
            self._show_popup("Save Failed", error_message)
            return

        if isinstance(user_payload, dict):
            self._apply_user_settings(user_payload)

        if self.is_admin_gate:
            platform_ok, platform_payload = platform_result
            if not platform_ok:
                error_message = self._extract_detail(platform_payload) or "Unable to save admin settings."
                self._set_feedback(error_message, "error")
                self._show_popup("Save Failed", error_message)
                return
            if isinstance(platform_payload, dict):
                self._apply_platform_settings(platform_payload)

        self._set_feedback("Settings saved successfully.", "success")
        self._show_popup("Settings Saved", "Your settings have been updated successfully.")

    def confirm_open_admin_dashboard(self):
        if not self.is_admin_gate:
            self._show_popup("Admin Only", "Admin tools are restricted to accounts with role='admin'.")
            return
        show_confirm_dialog(
            self,
            title="Open Admin Dashboard",
            message="This will open the admin dashboard. You must be signed in with an admin account.",
            confirm_label="Open Admin",
            cancel_label="Cancel",
            on_confirm=self.open_admin_dashboard,
        )

    def open_admin_dashboard(self):
        health = api_client.request("GET", "/", headers=None, timeout=3)
        if not health.get("ok"):
            self._show_popup(
                "Start Backend First",
                f"Admin tools need the backend running at {API_URL}.\n\nTip: run start_all.ps1 from the project root.",
            )
            return
        if not self.manager or not self.manager.has_screen("admin_dashboard"):
            self._show_popup("Admin Dashboard", "The admin dashboard screen is not available in this build.")
            return
        self.manager.current = "admin_dashboard"

    def open_change_pin_help(self):
        self._show_popup(
            "Change Transaction PIN",
            "The backend already supports PIN changes. If you want, I can add a dedicated PIN change form next.",
        )

    def confirm_logout(self):
        show_confirm_dialog(
            self,
            title="Confirm Sign Out",
            message="Do you want to sign out now? Your account will remain active.",
            confirm_label="Sign Out",
            cancel_label="Cancel",
            on_confirm=self.perform_logout,
        )

    def perform_logout(self):
        app = MDApp.get_running_app()
        token = str(getattr(app, "access_token", "") or "").strip()
        response = logout(token)
        app.access_token = ""
        app.pending_momo = ""
        save_token("")

        detail = ""
        if isinstance(response, dict):
            detail = str(response.get("message") or response.get("detail") or "").strip()

        self._show_popup(
            "Signed Out",
            detail or "You have been signed out successfully.",
            on_close=lambda: setattr(self.manager, "current", "login") if self.manager else None,
        )


Builder.load_string(KV)
