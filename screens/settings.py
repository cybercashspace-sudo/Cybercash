from __future__ import annotations

import threading

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import BooleanProperty, StringProperty
from kivymd.app import MDApp

from api.auth import logout
from api.client import API_URL, api_client, api_get
from core.bottom_nav import BottomNavBar
from core.popup_manager import show_confirm_dialog, show_message_dialog
from core.screen_actions import ActionScreen
from storage import save_token, clear_token

from kivymd.uix.card import MDCard
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
                padding: [dp(20), dp(20), dp(20), dp(120)]
                spacing: dp(20)

                MDLabel:
                    text: "SETTINGS"
                    font_style: "H5"
                    bold: True
                    theme_text_color: "Custom"
                    text_color: BRAND_GOLD
                    adaptive_height: True

                MDCard:
                    size_hint_y: None
                    height: dp(140)
                    radius: [dp(25)]
                    md_bg_color: PROFILE_BG
                    elevation: 0

                    MDBoxLayout:
                        spacing: dp(15)
                        padding: dp(15)

                        FitImage:
                            source: "assets/profile.png"
                            size_hint: None, None
                            size: dp(80), dp(80)
                            radius: [dp(40)]
                            pos_hint: {"center_y": .5}

                        MDBoxLayout:
                            orientation: "vertical"
                            pos_hint: {"center_y": .5}
                            MDLabel:
                                text: app.user_name
                                font_style: "H5"
                                bold: True
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                            MDLabel:
                                text: app.user_email
                                theme_text_color: "Hint"

                SettingsItem:
                    text: "Profile"
                    secondary: "Manage your personal info"
                    icon: "account-cog"
                    on_release: root.open_section("Profile")

                SettingsItem:
                    text: "Notifications"
                    secondary: "Alerts & preferences"
                    icon: "bell-outline"
                    on_release: root.open_section("Notifications")

                SettingsItem:
                    text: "Security"
                    secondary: "PIN, Biometrics & Privacy"
                    icon: "shield-lock-outline"
                    on_release: root.open_section("Security")

                SettingsItem:
                    text: "Help & Support"
                    secondary: "FAQs and contact us"
                    icon: "help-circle-outline"
                    on_release: root.open_section("Support")

                SettingsItem:
                    text: "About App"
                    secondary: "Version & legal"
                    icon: "information-outline"
                    on_release: root.open_section("About")

                SettingsItem:
                    text: "Logout"
                    secondary: "Secure session logout"
                    icon: "logout-variant"
                    on_release: root.confirm_logout()

                MDBoxLayout:
                    orientation: "vertical"
                    adaptive_height: True
                    spacing: dp(5)
                    padding: [0, dp(40), 0, 0]

                    MDLabel:
                        text: "Cyber Cash Technologies Ltd."
                        halign: "center"
                        theme_text_color: "Hint"
                        font_size: sp(13)
                    
                    MDLabel:
                        text: "Version 1.0.0"
                        halign: "center"
                        theme_text_color: "Hint"
                        font_size: sp(12)

                    MDLabel:
                        text: "© 2026 All Rights Reserved"
                        halign: "center"
                        theme_text_color: "Hint"
                        font_size: sp(11)

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

class SettingsItem(MDCard):
    text = StringProperty()
    secondary = StringProperty()
    icon = StringProperty()


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
        # Refresh local data
        app = MDApp.get_running_app()
        self.load_settings()

    def _show_popup(self, title: str, message: str, on_close=None):
        show_message_dialog(self, title=title, message=message, close_label="Close", on_close=on_close)

    def _set_admin_card_visible(self, visible: bool) -> None:
        # The new layout doesn't use the admin card directly, 
        # but we could add an Admin SettingsItem if needed.
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
        # We'll stick to a simple check for now
        app = MDApp.get_running_app()
        # If we had a role property on app, we'd use it here.
        # For now, we'll assume USER MODE as default in UI.
        pass

    def open_section(self, section_name: str):
        """Handles navigation to specific settings sub-sections/dialogs."""
        if section_name == "Security":
            self.open_security_dialog()
        else:
            self._show_popup(section_name, f"Manage your {section_name.lower()} settings. This section is coming soon.")

    def open_security_dialog(self):
        """Special handling for Security to include Privacy Mode toggle."""
        app = MDApp.get_running_app()
        content = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(15), padding=dp(20))
        
        # Re-using the Privacy Mode logic from before
        row = MDBoxLayout(size_hint_y=None, height=dp(42))
        row.add_widget(MDLabel(text="Privacy Mode (Task Switcher)", theme_text_color="Primary"))
        
        from kivymd.uix.selectioncontrol import MDSwitch
        switch = MDSwitch(active=app.privacy_mode)
        def _on_toggle(instance, value):
            app.privacy_mode = value
        switch.bind(active=_on_toggle)
        row.add_widget(switch)
        
        content.add_widget(row)
        content.add_widget(MDLabel(text="Change PIN and Biometrics settings can be accessed here.", theme_text_color="Secondary", font_size=sp(12)))

        show_custom_dialog(self, title="Security Settings", content_cls=content)

    def load_settings(self) -> None:
        if getattr(self, "_loading_settings", False):
            return
        self._loading_settings = True
        self._load_seq = int(getattr(self, "_load_seq", 0)) + 1
        seq = self._load_seq
        self._set_feedback("Loading your settings...", "info")
        threading.Thread(target=self._load_settings_worker, args=(seq,), daemon=True).start()

    def _load_settings_worker(self, seq: int) -> None:
        # Fetch both user profile and settings
        profile = self._request("GET", "/auth/me")
        settings_res = self._request("GET", "/settings/me")
        platform_res = (False, {})
        
        Clock.schedule_once(lambda _dt: self._apply_loaded_settings(seq, profile, settings_res))

    def _apply_loaded_settings(self, seq: int, user_result, platform_result) -> None:
        if seq != int(getattr(self, "_load_seq", 0)):
            return
        self._loading_settings = False

        user_ok, user_payload = user_result
        if not user_ok:
            self._set_feedback(self._extract_detail(user_payload) or "Unable to load your settings.", "error")
            return

        app = MDApp.get_running_app()
        if isinstance(user_payload, dict):
            app.user_name = user_payload.get("full_name") or user_payload.get("first_name") or app.user_name
            app.user_email = user_payload.get("email") or app.user_email

        self._set_feedback("Settings loaded.", "success")

    def _apply_user_settings(self, payload: dict) -> None:
        # Map backend settings to UI components if needed
        pass

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
        # Clear any pending wallet/deposit state so we don't accidentally resume
        # a pending deposit or create duplicate state after signing out.
        try:
            app.pending_wallet_action = ""
            app.pending_deposit_amount = ""
            app.pending_deposit_autostart = False
            app.wallet_entry_action = ""
        except Exception:
            pass
        clear_token()

        detail = ""
        if isinstance(response, dict):
            detail = str(response.get("message") or response.get("detail") or "").strip()

        self._show_popup(
            "Signed Out",
            detail or "You have been signed out successfully.",
            on_close=lambda: setattr(self.manager, "current", "login") if self.manager else None,
        )


Builder.load_string(KV)
