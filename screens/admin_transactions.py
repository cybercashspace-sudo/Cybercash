from __future__ import annotations

from datetime import datetime, timezone

from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import StringProperty
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel

from core.screen_actions import ActionScreen

KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp
#:set BG (0.03, 0.04, 0.06, 1)
#:set SURFACE (0.08, 0.10, 0.14, 0.95)
#:set GOLD (0.94, 0.79, 0.46, 1)
#:set TEXT_MAIN (0.95, 0.95, 0.95, 1)
#:set TEXT_SUB (0.74, 0.76, 0.80, 1)

<AdminTransactionsScreen>:
    MDBoxLayout:
        orientation: "vertical"

        canvas.before:
            Color:
                rgba: app.ui_background
            Rectangle:
                pos: self.pos
                size: self.size

        MDBoxLayout:
            size_hint_y: None
            height: dp(54 * root.layout_scale)
            padding: [dp(16 * root.layout_scale), dp(14 * root.layout_scale), dp(16 * root.layout_scale), 0]

            MDLabel:
                text: "Transaction Monitor"
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
            padding: [dp(16 * root.layout_scale), 0, dp(16 * root.layout_scale), 0]
            spacing: dp(8 * root.layout_scale)

            MDRaisedButton:
                text: "Refresh"
                on_release: root.load_transactions()

            MDLabel:
                text: root.summary_text
                halign: "right"
                theme_text_color: "Custom"
                text_color: app.ui_text_secondary

        ScrollView:
            do_scroll_x: False
            bar_width: 0

            MDBoxLayout:
                orientation: "vertical"
                adaptive_height: True
                padding: [dp(16 * root.layout_scale), dp(10 * root.layout_scale), dp(16 * root.layout_scale), dp(16 * root.layout_scale)]
                spacing: dp(12 * root.layout_scale)

                MDCard:
                    md_bg_color: app.ui_surface
                    radius: [dp(18 * root.layout_scale)]
                    elevation: 0
                    padding: [dp(12 * root.layout_scale)] * 4
                    adaptive_height: True

                    MDBoxLayout:
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: dp(8 * root.layout_scale)

                        MDLabel:
                            text: "Filters (optional)"
                            theme_text_color: "Custom"
                            text_color: app.gold
                            bold: True
                            adaptive_height: True

                        MDTextField:
                            id: user_id_field
                            hint_text: "User ID"
                            input_filter: "int"

                        MDTextField:
                            id: type_field
                            hint_text: "Type (e.g. funding, agent_withdrawal)"

                        MDTextField:
                            id: status_field
                            hint_text: "Status (e.g. completed, pending)"

                        MDRaisedButton:
                            text: "Apply Filters"
                            on_release: root.load_transactions()

                MDBoxLayout:
                    id: tx_list
                    orientation: "vertical"
                    adaptive_height: True
                    spacing: dp(10 * root.layout_scale)

                Widget:
                    size_hint_y: None
                    height: dp(8 * root.layout_scale)

        MDLabel:
            text: root.feedback_text
            theme_text_color: "Custom"
            text_color: root.feedback_color
            adaptive_height: True
            padding: [dp(16 * root.layout_scale), 0, dp(16 * root.layout_scale), dp(4 * root.layout_scale)]

        BottomNavBar:
            nav_variant: "admin"
            active_target: ""
            layout_scale: root.layout_scale
            text_scale: root.text_scale
            icon_scale: root.icon_scale
            bar_color: app.ui_surface
            active_color: app.gold
            inactive_color: app.ui_text_secondary
"""


class AdminTransactionsScreen(ActionScreen):
    summary_text = StringProperty("Loading...")

    def on_pre_enter(self):
        self.load_transactions()

    @staticmethod
    def _friendly_time(timestamp: str) -> str:
        raw = str(timestamp or "").strip()
        if not raw:
            return "—"
        try:
            dt_value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            tx_day = dt_value.astimezone(timezone.utc).date()
            if tx_day == now.date():
                return dt_value.strftime("Today %H:%M")
            if (now.date() - tx_day).days == 1:
                return dt_value.strftime("Yesterday %H:%M")
            return dt_value.strftime("%d %b %H:%M")
        except Exception:
            return "—"

    def _build_tx_card(self, tx: dict) -> MDCard:
        layout_scale = float(self.layout_scale or 1.0)
        text_scale = float(self.text_scale or 1.0)

        tx_id = int(tx.get("id", 0) or 0)
        user_id = int(tx.get("user_id", 0) or 0)
        tx_type = str(tx.get("type", "") or "").strip()
        status = str(tx.get("status", "") or "").strip()
        currency = str(tx.get("currency", "GHS") or "GHS").upper()
        timestamp = str(tx.get("timestamp", "") or "").strip()
        amount = float(tx.get("amount", 0.0) or 0.0)
        positive = amount >= 0
        amount_color = [0.54, 0.82, 0.67, 1] if positive else [0.96, 0.47, 0.42, 1]

        card = MDCard(
            size_hint_y=None,
            height=dp(112 * layout_scale),
            radius=[dp(16 * layout_scale)],
            md_bg_color=[0.08, 0.10, 0.14, 0.95],
            elevation=0,
            padding=[dp(12 * layout_scale), dp(10 * layout_scale), dp(12 * layout_scale), dp(10 * layout_scale)],
        )
        content = MDBoxLayout(orientation="vertical", spacing=dp(6 * layout_scale))
        header = MDBoxLayout(orientation="horizontal", spacing=dp(8 * layout_scale))
        header.add_widget(
            MDLabel(
                text=f"#{tx_id}  {tx_type or 'transaction'}",
                theme_text_color="Custom",
                text_color=[0.95, 0.95, 0.95, 1],
                bold=True,
                font_size=f"{15.0 * text_scale:.1f}sp",
            )
        )
        header.add_widget(
            MDLabel(
                text=f"{amount:,.2f} {currency}",
                theme_text_color="Custom",
                text_color=amount_color,
                halign="right",
                bold=True,
                font_size=f"{13.5 * text_scale:.1f}sp",
                size_hint_x=None,
                width=dp(165 * layout_scale),
            )
        )
        content.add_widget(header)
        content.add_widget(
            MDLabel(
                text=f"User {user_id}   |   {status or 'pending'}   |   {self._friendly_time(timestamp)}",
                theme_text_color="Custom",
                text_color=[0.74, 0.76, 0.80, 1],
                font_size=f"{11.5 * text_scale:.1f}sp",
            )
        )
        card.add_widget(content)
        return card

    def load_transactions(self) -> None:
        self._set_feedback("Loading transactions...", "info")
        params: dict[str, object] = {}

        user_id_raw = str(getattr(self.ids.user_id_field, "text", "") or "").strip()
        if user_id_raw.isdigit():
            params["user_id"] = int(user_id_raw)
        tx_type = str(getattr(self.ids.type_field, "text", "") or "").strip()
        if tx_type:
            params["type"] = tx_type
        tx_status = str(getattr(self.ids.status_field, "text", "") or "").strip()
        if tx_status:
            params["status"] = tx_status

        ok, payload = self._request("GET", "/admin/transactions", params=params or None)
        container = self.ids.tx_list
        container.clear_widgets()

        if ok and isinstance(payload, list):
            self.summary_text = f"{len(payload)} tx"
            if not payload:
                empty = MDCard(
                    size_hint_y=None,
                    height=dp(62 * float(self.layout_scale or 1.0)),
                    radius=[dp(14 * float(self.layout_scale or 1.0))],
                    md_bg_color=[0.08, 0.10, 0.14, 0.95],
                    elevation=0,
                )
                empty.add_widget(
                    MDLabel(
                        text="No transactions found for the selected filters.",
                        theme_text_color="Custom",
                        text_color=[0.74, 0.76, 0.80, 1],
                        halign="center",
                    )
                )
                container.add_widget(empty)
                self._set_feedback("No results.", "warning")
                return

            for tx in payload[:80]:
                if isinstance(tx, dict):
                    container.add_widget(self._build_tx_card(tx))
            self._set_feedback("Transactions loaded.", "success")
            return

        detail = self._extract_detail(payload) or "Unable to load transactions."
        self.summary_text = "Sync failed"
        self._set_feedback(detail, "error")
        self._show_popup("Transactions", detail)


Builder.load_string(KV)
