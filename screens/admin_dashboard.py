from __future__ import annotations

from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import StringProperty
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel

from core.screen_actions import ActionScreen

KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp
#:set BG (0.03, 0.04, 0.06, 1)
#:set SURFACE (0.08, 0.10, 0.14, 0.95)
#:set SURFACE_SOFT (0.12, 0.14, 0.18, 0.95)
#:set GREEN_CARD (0.12, 0.24, 0.18, 0.98)
#:set GREEN_CARD_SOFT (0.09, 0.17, 0.13, 0.92)
#:set GOLD (0.94, 0.79, 0.46, 1)
#:set TEXT_MAIN (0.95, 0.95, 0.95, 1)
#:set TEXT_SUB (0.74, 0.76, 0.80, 1)

<AdminDashboardScreen>:
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
                adaptive_height: True
                spacing: dp(12 * root.layout_scale)
                padding: [dp(16 * root.layout_scale), dp(18 * root.layout_scale), dp(16 * root.layout_scale), dp(18 * root.layout_scale)]

                MDLabel:
                    text: "ADMIN DASHBOARD"
                    halign: "center"
                    theme_text_color: "Custom"
                    text_color: app.gold
                    font_style: "Title"
                    font_size: sp(22 * root.text_scale)
                    bold: True
                    adaptive_height: True

                MDBoxLayout:
                    adaptive_height: True
                    spacing: dp(10 * root.layout_scale)

                    MDCard:
                        radius: [dp(18 * root.layout_scale)]
                        md_bg_color: app.ui_surface
                        elevation: 0
                        ripple_behavior: True
                        padding: [dp(12 * root.layout_scale), dp(10 * root.layout_scale)]
                        size_hint_y: None
                        height: dp(56 * root.layout_scale)
                        on_release: root.open_admin_profile()

                        MDBoxLayout:
                            spacing: dp(8 * root.layout_scale)
                            MDIconButton:
                                icon: "shield-account"
                                theme_text_color: "Custom"
                                text_color: app.gold
                                disabled: True
                            MDLabel:
                                text: "Admin Profile"
                                theme_text_color: "Custom"
                                text_color: app.ui_text_primary
                                bold: True
                                valign: "middle"

                    MDCard:
                        radius: [dp(18 * root.layout_scale)]
                        md_bg_color: app.ui_surface
                        elevation: 0
                        ripple_behavior: True
                        padding: [dp(12 * root.layout_scale), dp(10 * root.layout_scale)]
                        size_hint_y: None
                        height: dp(56 * root.layout_scale)
                        on_release: root.open_admin_notifications()

                        MDBoxLayout:
                            spacing: dp(8 * root.layout_scale)
                            MDIconButton:
                                icon: "bell-ring-outline"
                                theme_text_color: "Custom"
                                text_color: app.gold
                                disabled: True
                            MDLabel:
                                text: "Notifications"
                                theme_text_color: "Custom"
                                text_color: app.ui_text_primary
                                bold: True
                                valign: "middle"

                MDCard:
                    radius: [dp(20 * root.layout_scale)]
                    size_hint_y: None
                    height: dp(126 * root.layout_scale)
                    md_bg_color: app.ui_glass
                    elevation: 0
                    padding: [dp(14 * root.layout_scale)] * 4

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(6 * root.layout_scale)

                        MDLabel:
                            text: "Total Platform Balance"
                            theme_text_color: "Custom"
                            text_color: app.ui_text_primary
                            adaptive_height: True

                        MDLabel:
                            text: root.platform_balance_text
                            theme_text_color: "Custom"
                            text_color: app.gold
                            font_style: "Title"
                            font_size: sp(28 * root.text_scale)
                            bold: True
                            adaptive_height: True

                        MDLabel:
                            text: "System liquidity (GHS wallets + escrow + investments)"
                            theme_text_color: "Custom"
                            text_color: app.ui_text_secondary
                            font_size: sp(12 * root.text_scale)
                            adaptive_height: True

                MDGridLayout:
                    cols: 2
                    adaptive_height: True
                    row_default_height: dp(92 * root.layout_scale)
                    row_force_default: True
                    spacing: dp(10 * root.layout_scale)

                    MDCard:
                        md_bg_color: app.ui_surface_soft
                        radius: [dp(16 * root.layout_scale)]
                        elevation: 0
                        padding: [dp(12 * root.layout_scale)] * 4
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(4 * root.layout_scale)
                            MDLabel:
                                text: "Total Users"
                                theme_text_color: "Custom"
                                text_color: app.ui_text_secondary
                            MDLabel:
                                text: root.total_users_text
                                theme_text_color: "Custom"
                                text_color: app.ui_text_primary
                                font_style: "Title"
                                bold: True

                    MDCard:
                        md_bg_color: app.ui_surface_soft
                        radius: [dp(16 * root.layout_scale)]
                        elevation: 0
                        padding: [dp(12 * root.layout_scale)] * 4
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(4 * root.layout_scale)
                            MDLabel:
                                text: "Total Agents"
                                theme_text_color: "Custom"
                                text_color: app.ui_text_secondary
                            MDLabel:
                                text: root.total_agents_text
                                theme_text_color: "Custom"
                                text_color: app.ui_text_primary
                                font_style: "Title"
                                bold: True

                    MDCard:
                        md_bg_color: app.ui_surface_soft
                        radius: [dp(16 * root.layout_scale)]
                        elevation: 0
                        padding: [dp(12 * root.layout_scale)] * 4
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(4 * root.layout_scale)
                            MDLabel:
                                text: "Active Agents"
                                theme_text_color: "Custom"
                                text_color: app.ui_text_secondary
                            MDLabel:
                                text: root.active_agents_text
                                theme_text_color: "Custom"
                                text_color: app.ui_text_primary
                                font_style: "Title"
                                bold: True

                    MDCard:
                        md_bg_color: app.ui_surface_soft
                        radius: [dp(16 * root.layout_scale)]
                        elevation: 0
                        padding: [dp(12 * root.layout_scale)] * 4
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(4 * root.layout_scale)
                            MDLabel:
                                text: "Total Deposits"
                                theme_text_color: "Custom"
                                text_color: app.ui_text_secondary
                            MDLabel:
                                text: root.total_deposits_text
                                theme_text_color: "Custom"
                                text_color: app.ui_text_primary
                                font_style: "Title"
                                bold: True

                    MDCard:
                        md_bg_color: app.ui_surface_soft
                        radius: [dp(16 * root.layout_scale)]
                        elevation: 0
                        padding: [dp(12 * root.layout_scale)] * 4
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(4 * root.layout_scale)
                            MDLabel:
                                text: "Admin Revenue"
                                theme_text_color: "Custom"
                                text_color: app.ui_text_secondary
                            MDLabel:
                                text: root.revenue_text
                                theme_text_color: "Custom"
                                text_color: app.gold
                                font_style: "Title"
                                bold: True

                    MDCard:
                        md_bg_color: app.ui_surface_soft
                        radius: [dp(16 * root.layout_scale)]
                        elevation: 0
                        padding: [dp(12 * root.layout_scale)] * 4
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(4 * root.layout_scale)
                            MDLabel:
                                text: "Withdrawals"
                                theme_text_color: "Custom"
                                text_color: app.ui_text_secondary
                            MDLabel:
                                text: root.withdrawals_text
                                theme_text_color: "Custom"
                                text_color: app.ui_text_primary
                                font_style: "Title"
                                bold: True

                    MDCard:
                        md_bg_color: app.ui_surface_soft
                        radius: [dp(16 * root.layout_scale)]
                        elevation: 0
                        padding: [dp(12 * root.layout_scale)] * 4
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(4 * root.layout_scale)
                            MDLabel:
                                text: "BTC Volume"
                                theme_text_color: "Custom"
                                text_color: app.ui_text_secondary
                            MDLabel:
                                text: root.btc_volume_text
                                theme_text_color: "Custom"
                                text_color: app.gold
                                font_style: "Title"
                                bold: True

                MDCard:
                    radius: [dp(20 * root.layout_scale)]
                    md_bg_color: app.ui_surface
                    elevation: 0
                    padding: [dp(14 * root.layout_scale)] * 4
                    adaptive_height: True

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(6 * root.layout_scale)
                        adaptive_height: True

                        MDBoxLayout:
                            adaptive_height: True
                            spacing: dp(10 * root.layout_scale)

                            MDLabel:
                                text: "Binance BTC Wallet"
                                theme_text_color: "Custom"
                                text_color: app.gold
                                font_style: "Title"
                                font_size: sp(16 * root.text_scale)
                                bold: True
                                adaptive_height: True

                            Widget:

                            MDTextButton:
                                text: "Copy Address"
                                theme_text_color: "Custom"
                                text_color: app.gold
                                on_release: root.copy_binance_btc_address()

                        MDLabel:
                            text: root.binance_btc_status_text
                            theme_text_color: "Custom"
                            text_color: app.ui_text_secondary
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                        MDLabel:
                            text: root.binance_btc_balance_text
                            theme_text_color: "Custom"
                            text_color: app.ui_text_primary
                            font_style: "Title"
                            font_size: sp(22 * root.text_scale)
                            bold: True
                            adaptive_height: True

                        MDLabel:
                            text: root.binance_btc_price_text + "  |  " + root.binance_btc_ghs_value_text
                            theme_text_color: "Custom"
                            text_color: app.ui_text_secondary
                            font_size: sp(12 * root.text_scale)
                            adaptive_height: True

                        MDLabel:
                            text: root.binance_btc_address_text
                            text_size: self.width, None
                            halign: "left"
                            theme_text_color: "Custom"
                            text_color: app.ui_text_primary
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                MDLabel:
                    text: "Quick Admin Actions"
                    theme_text_color: "Custom"
                    text_color: app.gold
                    font_style: "Title"
                    font_size: sp(18 * root.text_scale)
                    bold: True
                    adaptive_height: True

                MDGridLayout:
                    cols: 2
                    adaptive_height: True
                    row_default_height: dp(118 * root.layout_scale)
                    row_force_default: True
                    spacing: dp(10 * root.layout_scale)

                    MDCard:
                        radius: [dp(16 * root.layout_scale)]
                        md_bg_color: app.ui_surface_soft
                        elevation: 0
                        ripple_behavior: True
                        padding: [dp(8 * root.layout_scale)] * 4
                        on_release: root.open_withdrawals()
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(2 * root.layout_scale)
                            MDIconButton:
                                icon: "cash-refund"
                                theme_text_color: "Custom"
                                text_color: app.gold
                                pos_hint: {"center_x": 0.5}
                                disabled: True
                            MDLabel:
                                text: "Approve\\nWithdrawals"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: app.ui_text_primary
                                bold: True

                    MDCard:
                        radius: [dp(16 * root.layout_scale)]
                        md_bg_color: app.ui_surface_soft
                        elevation: 0
                        ripple_behavior: True
                        padding: [dp(8 * root.layout_scale)] * 4
                        on_release: root.open_agents()
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(2 * root.layout_scale)
                            MDIconButton:
                                icon: "account-tie"
                                theme_text_color: "Custom"
                                text_color: app.gold
                                pos_hint: {"center_x": 0.5}
                                disabled: True
                            MDLabel:
                                text: "Manage\\nAgents"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: app.ui_text_primary
                                bold: True

                    MDCard:
                        radius: [dp(16 * root.layout_scale)]
                        md_bg_color: app.ui_surface_soft
                        elevation: 0
                        ripple_behavior: True
                        padding: [dp(8 * root.layout_scale)] * 4
                        on_release: root.open_users()
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(2 * root.layout_scale)
                            MDIconButton:
                                icon: "account-group"
                                theme_text_color: "Custom"
                                text_color: app.gold
                                pos_hint: {"center_x": 0.5}
                                disabled: True
                            MDLabel:
                                text: "Manage\\nUsers"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: app.ui_text_primary
                                bold: True

                    MDCard:
                        radius: [dp(16 * root.layout_scale)]
                        md_bg_color: app.ui_surface_soft
                        elevation: 0
                        ripple_behavior: True
                        padding: [dp(8 * root.layout_scale)] * 4
                        on_release: root.open_transactions()
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(2 * root.layout_scale)
                            MDIconButton:
                                icon: "swap-horizontal"
                                theme_text_color: "Custom"
                                text_color: app.gold
                                pos_hint: {"center_x": 0.5}
                                disabled: True
                            MDLabel:
                                text: "Transaction\\nMonitor"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: app.ui_text_primary
                                bold: True

                    MDCard:
                        radius: [dp(16 * root.layout_scale)]
                        md_bg_color: app.ui_surface_soft
                        elevation: 0
                        ripple_behavior: True
                        padding: [dp(8 * root.layout_scale)] * 4
                        on_release: root.open_revenue()
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(2 * root.layout_scale)
                            MDIconButton:
                                icon: "chart-line"
                                theme_text_color: "Custom"
                                text_color: app.gold
                                pos_hint: {"center_x": 0.5}
                                disabled: True
                            MDLabel:
                                text: "Revenue\\nAnalytics"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: app.ui_text_primary
                                bold: True

                    MDCard:
                        radius: [dp(16 * root.layout_scale)]
                        md_bg_color: app.ui_surface_soft
                        elevation: 0
                        ripple_behavior: True
                        padding: [dp(8 * root.layout_scale)] * 4
                        on_release: root.open_fraud_alerts()
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(2 * root.layout_scale)
                            MDIconButton:
                                icon: "shield-alert-outline"
                                theme_text_color: "Custom"
                                text_color: app.gold
                                pos_hint: {"center_x": 0.5}
                                disabled: True
                            MDLabel:
                                text: "Fraud\\nAlerts"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: app.ui_text_primary
                                bold: True

                MDLabel:
                    text: "Platform Activity"
                    theme_text_color: "Custom"
                    text_color: app.gold
                    font_style: "Title"
                    font_size: sp(18 * root.text_scale)
                    bold: True
                    adaptive_height: True

                MDCard:
                    radius: [dp(18 * root.layout_scale)]
                    md_bg_color: app.ui_surface
                    elevation: 0
                    padding: [dp(12 * root.layout_scale)] * 4
                    adaptive_height: True

                    MDBoxLayout:
                        id: activity_list
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: dp(6 * root.layout_scale)

                MDLabel:
                    text: root.feedback_text
                    theme_text_color: "Custom"
                    text_color: root.feedback_color
                    adaptive_height: True

                Widget:
                    size_hint_y: None
                    height: dp(8 * root.layout_scale)

        BottomNavBar:
            nav_variant: "admin"
            active_target: "admin_dashboard"
            layout_scale: root.layout_scale
            text_scale: root.text_scale
            icon_scale: root.icon_scale
            bar_color: app.ui_surface
            active_color: app.gold
            inactive_color: app.ui_text_secondary
"""


class AdminDashboardScreen(ActionScreen):
    platform_balance_text = StringProperty("GHS 0.00")
    total_users_text = StringProperty("0")
    total_agents_text = StringProperty("0")
    active_agents_text = StringProperty("0")
    total_deposits_text = StringProperty("GHS 0.00")
    revenue_text = StringProperty("GHS 0.00")
    withdrawals_text = StringProperty("GHS 0.00")
    btc_volume_text = StringProperty("0.00 BTC")

    binance_btc_status_text = StringProperty("Checking Binance connection...")
    binance_btc_balance_text = StringProperty("BTC 0.0000")
    binance_btc_price_text = StringProperty("BTC/USDT $0.00")
    binance_btc_ghs_value_text = StringProperty("~ GHS 0.00")
    binance_btc_address_text = StringProperty("Address: --")

    _refresh_event = None
    _binance_refresh_event = None
    _binance_btc_address_raw = ""

    def on_pre_enter(self):
        self.load_dashboard()
        if self._refresh_event is None:
            self._refresh_event = Clock.schedule_interval(lambda _dt: self.load_dashboard(silent=True), 30)
        self.refresh_binance_btc(silent=True)
        if self._binance_refresh_event is None:
            self._binance_refresh_event = Clock.schedule_interval(
                lambda _dt: self.refresh_binance_btc(silent=True),
                10,
            )

    def on_pre_leave(self):
        if self._refresh_event is not None:
            try:
                self._refresh_event.cancel()
            except Exception:
                pass
            self._refresh_event = None

        if self._binance_refresh_event is not None:
            try:
                self._binance_refresh_event.cancel()
            except Exception:
                pass
            self._binance_refresh_event = None

    @staticmethod
    def _format_ghs(value: object) -> str:
        try:
            amount = float(value or 0.0)
        except Exception:
            amount = 0.0
        return f"GHS {amount:,.2f}"

    @staticmethod
    def _format_btc(value: object) -> str:
        try:
            amount = float(value or 0.0)
        except Exception:
            amount = 0.0
        return f"{amount:,.4f} BTC"

    def _goto(self, screen_name: str, *, title: str = "Admin Tools") -> None:
        manager = self.manager
        if not manager or not manager.has_screen(screen_name):
            self._show_popup(title, f"Screen '{screen_name}' is not available in this build.")
            return
        manager.current = screen_name

    def load_dashboard(self, *, silent: bool = False):
        if not silent:
            self._set_feedback("Loading admin metrics...", "info")

        ok, payload = self._request("GET", "/admin/dashboard")
        if not ok or not isinstance(payload, dict):
            detail = self._extract_detail(payload) or "Unable to load admin dashboard."
            self._set_feedback(detail, "error")
            self._show_popup("Admin Dashboard", detail)
            self.go_back()
            return

        self.platform_balance_text = self._format_ghs(payload.get("platform_balance", 0.0))
        self.total_users_text = f"{int(payload.get('users', 0) or 0):,}"
        self.total_agents_text = f"{int(payload.get('agents', 0) or 0):,}"
        self.active_agents_text = f"{int(payload.get('active_agents', 0) or 0):,}"
        self.total_deposits_text = self._format_ghs(payload.get("total_deposits", 0.0))
        self.revenue_text = self._format_ghs(payload.get("revenue", 0.0))
        self.withdrawals_text = self._format_ghs(payload.get("withdrawals", 0.0))
        self.btc_volume_text = self._format_btc(payload.get("btc_volume", 0.0))

        activity_container = self.ids.activity_list
        activity_container.clear_widgets()
        activity = payload.get("activity", [])
        if isinstance(activity, list) and activity:
            for item in activity[:6]:
                label = str((item or {}).get("label", "") or "").strip() or "Activity"
                amount = (item or {}).get("amount", 0.0)
                row = MDBoxLayout(orientation="horizontal", size_hint_y=None, height=dp(26 * float(self.layout_scale or 1.0)))
                row.add_widget(
                    MDLabel(
                        text=f"\u2022 {label}",
                        theme_text_color="Custom",
                        text_color=[0.74, 0.76, 0.80, 1],
                        halign="left",
                    )
                )
                row.add_widget(
                    MDLabel(
                        text=self._format_ghs(amount),
                        theme_text_color="Custom",
                        text_color=[0.94, 0.79, 0.46, 1],
                        halign="right",
                        size_hint_x=None,
                        width=dp(130 * float(self.layout_scale or 1.0)),
                    )
                )
                activity_container.add_widget(row)
        else:
            activity_container.add_widget(
                MDLabel(
                    text="No recent activity yet.",
                    theme_text_color="Custom",
                    text_color=[0.74, 0.76, 0.80, 1],
                    halign="center",
                    adaptive_height=True,
                )
            )

        if not silent:
            self._set_feedback("Admin dashboard refreshed.", "success")

    def refresh_binance_btc(self, *, silent: bool = False) -> None:
        ok, payload = self._request("GET", "/admin/binance/btc/dashboard")
        if not ok or not isinstance(payload, dict):
            detail = self._extract_detail(payload) or "Unable to load Binance BTC dashboard."
            self.binance_btc_status_text = f"Binance error: {detail}"
            if not silent:
                self._set_feedback(detail, "warning")
            return

        configured = bool(payload.get("configured"))
        btc_balance = float(payload.get("btc_balance", 0.0) or 0.0)
        btc_locked = float(payload.get("btc_locked", 0.0) or 0.0)
        usd_price = float(payload.get("usd_price", 0.0) or 0.0)
        ghs_value = float(payload.get("ghs_value", 0.0) or 0.0)
        address = str(payload.get("address") or "").strip()
        updated_at = str(payload.get("updated_at") or "").strip()

        self._binance_btc_address_raw = address
        if not configured:
            self.binance_btc_status_text = "Binance not configured (set BINANCE_API_KEY and BINANCE_SECRET_KEY)."
        else:
            refreshed = f"Updated {updated_at}" if updated_at else "Updated recently"
            self.binance_btc_status_text = f"Binance connected. {refreshed}"

        self.binance_btc_balance_text = f"BTC {btc_balance:,.6f} (locked {btc_locked:,.6f})"
        self.binance_btc_price_text = f"BTC/USDT ${usd_price:,.2f}"
        self.binance_btc_ghs_value_text = f"~ GHS {ghs_value:,.2f}"
        self.binance_btc_address_text = f"Address: {address or '--'}"

    def copy_binance_btc_address(self) -> None:
        address = str(getattr(self, "_binance_btc_address_raw", "") or "").strip()
        if not address:
            self._set_feedback("Binance BTC address not available yet.", "warning")
            return
        Clipboard.copy(address)
        self._set_feedback("Binance BTC address copied.", "success")

    def open_admin_profile(self):
        self._show_popup("Admin Profile", "Admin tools are restricted to accounts with role='admin'.")

    def open_admin_notifications(self):
        self._show_popup("Notifications", "No notifications configured yet.")

    def open_withdrawals(self):
        self._goto("admin_withdrawals", title="Withdrawals")

    def open_agents(self):
        self._goto("admin_agents", title="Agents")

    def open_users(self):
        self._goto("admin_users", title="Users")

    def open_transactions(self):
        self._goto("admin_transactions", title="Transactions")

    def open_revenue(self):
        self._goto("admin_revenue", title="Revenue")

    def open_fraud_alerts(self):
        self._goto("admin_fraud_alerts", title="Fraud Alerts")


Builder.load_string(KV)
