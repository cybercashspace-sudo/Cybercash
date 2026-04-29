from __future__ import annotations

from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import StringProperty
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel

from core.screen_actions import ActionScreen

KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp
#:set BG (0.03, 0.04, 0.06, 1)
#:set SURFACE (0.08, 0.10, 0.14, 0.95)
#:set GREEN_CARD (0.12, 0.24, 0.18, 0.98)
#:set GREEN_CARD_SOFT (0.09, 0.17, 0.13, 0.92)
#:set GOLD (0.94, 0.79, 0.46, 1)
#:set TEXT_MAIN (0.95, 0.95, 0.95, 1)
#:set TEXT_SUB (0.74, 0.76, 0.80, 1)

<AdminRevenueScreen>:
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

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(52 * root.layout_scale)

                    MDLabel:
                        text: "Revenue Analytics"
                        font_style: "Title"
                        font_size: sp(22 * root.text_scale)
                        bold: True
                        theme_text_color: "Custom"
                        text_color: app.gold

                    MDTextButton:
                        text: "Back"
                        theme_text_color: "Custom"
                        text_color: app.gold
                        on_release: root.go_back()

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(44 * root.layout_scale)
                    spacing: dp(8 * root.layout_scale)

                    MDRaisedButton:
                        text: "Refresh"
                        on_release: root.load_revenue()

                    MDLabel:
                        text: root.summary_text
                        halign: "right"
                        theme_text_color: "Custom"
                        text_color: app.ui_text_secondary

                MDCard:
                    radius: [dp(20 * root.layout_scale)]
                    size_hint_y: None
                    height: dp(120 * root.layout_scale)
                    md_bg_color: app.ui_glass
                    elevation: 0
                    padding: [dp(14 * root.layout_scale)] * 4

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(6 * root.layout_scale)

                        MDLabel:
                            text: "Platform Balance"
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
                                text: "Total Deposits"
                                theme_text_color: "Custom"
                                text_color: app.ui_text_secondary
                            MDLabel:
                                text: root.deposits_text
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
                                text: "Total Withdrawals"
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

                MDLabel:
                    text: "Ledger Accounts"
                    theme_text_color: "Custom"
                    text_color: app.gold
                    font_style: "Title"
                    font_size: sp(18 * root.text_scale)
                    bold: True
                    adaptive_height: True

                MDBoxLayout:
                    id: accounts_list
                    orientation: "vertical"
                    adaptive_height: True
                    spacing: dp(10 * root.layout_scale)

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
            active_target: "admin_revenue"
            layout_scale: root.layout_scale
            text_scale: root.text_scale
            icon_scale: root.icon_scale
            bar_color: app.ui_surface
            active_color: app.gold
            inactive_color: app.ui_text_secondary
"""


class AdminRevenueScreen(ActionScreen):
    summary_text = StringProperty("Loading...")
    platform_balance_text = StringProperty("GHS 0.00")
    revenue_text = StringProperty("GHS 0.00")
    deposits_text = StringProperty("GHS 0.00")
    withdrawals_text = StringProperty("GHS 0.00")
    btc_volume_text = StringProperty("0.0000 BTC")

    def on_pre_enter(self):
        self.load_revenue()

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

    def _build_account_card(self, account: dict) -> MDCard:
        layout_scale = float(self.layout_scale or 1.0)
        text_scale = float(self.text_scale or 1.0)

        name = str(account.get("name", "") or "").strip() or "Account"
        acc_type = str(account.get("type", "") or "").strip() or "—"
        balance = self._format_ghs(account.get("balance", 0.0))

        card = MDCard(
            size_hint_y=None,
            height=dp(84 * layout_scale),
            radius=[dp(16 * layout_scale)],
            md_bg_color=[0.08, 0.10, 0.14, 0.95],
            elevation=0,
            padding=[dp(12 * layout_scale), dp(10 * layout_scale), dp(12 * layout_scale), dp(10 * layout_scale)],
        )
        content = MDBoxLayout(orientation="horizontal", spacing=dp(8 * layout_scale))
        meta = MDBoxLayout(orientation="vertical", spacing=dp(3 * layout_scale))
        meta.add_widget(
            MDLabel(
                text=name,
                theme_text_color="Custom",
                text_color=[0.95, 0.95, 0.95, 1],
                bold=True,
                font_size=f"{14.5 * text_scale:.1f}sp",
            )
        )
        meta.add_widget(
            MDLabel(
                text=acc_type,
                theme_text_color="Custom",
                text_color=[0.74, 0.76, 0.80, 1],
                font_size=f"{11.0 * text_scale:.1f}sp",
            )
        )
        content.add_widget(meta)
        content.add_widget(
            MDLabel(
                text=balance,
                theme_text_color="Custom",
                text_color=[0.94, 0.79, 0.46, 1],
                bold=True,
                halign="right",
                font_size=f"{13.0 * text_scale:.1f}sp",
                size_hint_x=None,
                width=dp(170 * layout_scale),
            )
        )
        card.add_widget(content)
        return card

    def load_revenue(self) -> None:
        self._set_feedback("Loading revenue metrics...", "info")

        ok_dashboard, dashboard = self._request("GET", "/admin/dashboard")
        ok_accounts, accounts = self._request("GET", "/admin/accounts")

        if ok_dashboard and isinstance(dashboard, dict):
            self.platform_balance_text = self._format_ghs(dashboard.get("platform_balance", 0.0))
            self.revenue_text = self._format_ghs(dashboard.get("revenue", 0.0))
            self.deposits_text = self._format_ghs(dashboard.get("total_deposits", 0.0))
            self.withdrawals_text = self._format_ghs(dashboard.get("withdrawals", 0.0))
            self.btc_volume_text = self._format_btc(dashboard.get("btc_volume", 0.0))

        accounts_container = self.ids.accounts_list
        accounts_container.clear_widgets()

        if ok_accounts and isinstance(accounts, list) and accounts:
            self.summary_text = f"{len(accounts)} account(s)"
            for acc in accounts[:60]:
                if isinstance(acc, dict):
                    accounts_container.add_widget(self._build_account_card(acc))
            self._set_feedback("Revenue analytics updated.", "success")
            return

        if ok_accounts and isinstance(accounts, list):
            self.summary_text = "0 account(s)"
            placeholder = MDCard(
                size_hint_y=None,
                height=dp(62 * float(self.layout_scale or 1.0)),
                radius=[dp(14 * float(self.layout_scale or 1.0))],
                md_bg_color=[0.08, 0.10, 0.14, 0.95],
                elevation=0,
            )
            placeholder.add_widget(
                MDLabel(
                    text="No ledger accounts found yet.",
                    theme_text_color="Custom",
                    text_color=[0.74, 0.76, 0.80, 1],
                    halign="center",
                )
            )
            accounts_container.add_widget(placeholder)
            self._set_feedback("No ledger accounts.", "warning")
            return

        detail = self._extract_detail(accounts if not ok_accounts else dashboard) or "Unable to load revenue analytics."
        self.summary_text = "Sync failed"
        self._set_feedback(detail, "error")
        self._show_popup("Revenue Analytics", detail)


Builder.load_string(KV)
