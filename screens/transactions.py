import json
from datetime import datetime, timezone

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
#:set SURFACE_SOFT (0.12, 0.14, 0.18, 0.95)
#:set GOLD (0.94, 0.79, 0.46, 1)
#:set TEXT_MAIN (0.95, 0.95, 0.95, 1)
#:set TEXT_SUB (0.74, 0.76, 0.80, 1)
<TransactionScreen>:
    MDBoxLayout:
        orientation: "vertical"
        padding: [dp(16 * root.layout_scale), dp(16 * root.layout_scale), dp(16 * root.layout_scale), dp(12 * root.layout_scale)]
        spacing: dp(10 * root.layout_scale)

        canvas.before:
            Color:
                rgba: BG
            Rectangle:
                pos: self.pos
                size: self.size

        MDBoxLayout:
            size_hint_y: None
            height: dp(50 * root.layout_scale)

            MDLabel:
                text: "Transaction History"
                font_style: "Title"
                font_size: sp(22 * root.text_scale)
                bold: True
                theme_text_color: "Custom"
                text_color: GOLD

            MDTextButton:
                text: "Back"
                theme_text_color: "Custom"
                text_color: GOLD
                on_release: root.go_back()

        MDBoxLayout:
            size_hint_y: None
            height: dp(44 * root.layout_scale)
            spacing: dp(8 * root.layout_scale)

            MDRaisedButton:
                text: "Refresh"
                on_release: root.load_transactions()

            MDLabel:
                text: root.summary_text
                halign: "right"
                theme_text_color: "Custom"
                text_color: TEXT_SUB

        ScrollView:
            do_scroll_x: False
            bar_width: 0

            MDBoxLayout:
                id: tx_list
                orientation: "vertical"
                spacing: "8dp"
                adaptive_height: True

        MDLabel:
            text: root.feedback_text
            theme_text_color: "Custom"
            text_color: root.feedback_color
            adaptive_height: True

        BottomNavBar:
            nav_variant: "default"
            active_target: ""
            layout_scale: root.layout_scale
            text_scale: root.text_scale
            icon_scale: root.icon_scale
"""


class TransactionScreen(ActionScreen):
    summary_text = StringProperty("Loading...")

    def on_pre_enter(self):
        self.load_transactions()

    @staticmethod
    def _friendly_time(timestamp: str) -> str:
        raw = str(timestamp or "").strip()
        if not raw:
            return "Recent"
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
            return "Recent"

    @staticmethod
    def _parse_metadata(tx: dict) -> dict:
        raw_metadata = tx.get("metadata_json")
        if isinstance(raw_metadata, dict):
            return raw_metadata
        if isinstance(raw_metadata, str) and raw_metadata.strip():
            try:
                parsed = json.loads(raw_metadata)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                return {}
        return {}

    @staticmethod
    def _format_currency(value: object) -> str:
        try:
            amount = float(value or 0.0)
        except Exception:
            amount = 0.0
        return f"{amount:,.2f}"

    def _friendly_title(self, tx: dict) -> str:
        key = str(tx.get("type", "") or "").strip().lower()
        metadata = self._parse_metadata(tx)
        if key == "transfer":
            transfer_kind = str(metadata.get("transfer_kind", "") or "").strip().lower()
            direction = str(metadata.get("direction", "") or "").strip().lower()
            if transfer_kind == "withdraw_to_agent":
                return "Agent Withdrawal Received" if direction == "receive" else "Withdraw To Agent"
            if transfer_kind == "wallet_transfer":
                return "P2P Received" if direction == "receive" else "P2P Transfer"
            return "Transfer Received" if direction == "receive" else "Funds Transfer"

        mapping = {
            "agent_deposit": "Deposit from Agent",
            "agent_withdrawal": "Agent Withdrawal",
            "funding": "Paystack Deposit",
            "airtime": "Airtime Purchase",
            "data": "Data Bundle Purchase",
            "investment_create": "Investment Deposit",
            "investment_payout": "Investment Payout",
            "escrow_create": "Escrow Created",
            "escrow_release": "Escrow Released",
            "card_spend": "Card Spend",
        }
        return mapping.get(key, key.replace("_", " ").title() if key else "Transaction")

    def _transfer_breakdown_text(self, tx: dict) -> str:
        tx_type = str(tx.get("type", "") or "").strip().lower()
        if tx_type != "transfer":
            return ""

        metadata = self._parse_metadata(tx)
        transfer_kind = str(metadata.get("transfer_kind", "") or "").strip().lower()
        direction = str(metadata.get("direction", "") or "").strip().lower()
        if transfer_kind not in {"withdraw_to_agent", "wallet_transfer"} or direction != "send":
            return ""

        transferred_amount = metadata.get("transferred_amount", 0.0)
        transfer_fee = metadata.get("transfer_fee", 0.0)
        transfer_fee_rate = float(metadata.get("transfer_fee_rate", 0.0) or 0.0)
        total_debited = metadata.get("total_debited", tx.get("amount", 0.0))
        fee_label = f"Fee ({transfer_fee_rate * 100:.1f}%)" if transfer_fee_rate > 0 else "Fee"
        if transfer_kind == "wallet_transfer" and transfer_fee_rate > 0:
            try:
                feeable_amount = float(metadata.get("p2p_feeable_amount", 0.0) or 0.0)
            except Exception:
                feeable_amount = 0.0
            if feeable_amount > 0:
                fee_label = f"Fee ({transfer_fee_rate * 100:.1f}% on GHS {self._format_currency(feeable_amount)})"
            elif float(transfer_fee or 0.0) <= 0:
                fee_label = "Fee (free today)"
        return (
            f"Amt GHS {self._format_currency(transferred_amount)} | "
            f"{fee_label} GHS {self._format_currency(transfer_fee)} | "
            f"Total GHS {self._format_currency(total_debited)}"
        )

    def _build_item(self, tx: dict) -> MDCard:
        amount = float(tx.get("amount", 0.0) or 0.0)
        positive = amount >= 0
        amount_color = [0.54, 0.82, 0.67, 1] if positive else [0.96, 0.47, 0.42, 1]
        sign = "+" if positive else "-"
        detail_text = self._transfer_breakdown_text(tx)
        layout_scale = float(self.layout_scale or 1.0)
        text_scale = float(self.text_scale or 1.0)

        card = MDCard(
            size_hint_y=None,
            height=dp((96 if detail_text else 78) * layout_scale),
            radius=[dp(14 * layout_scale)],
            md_bg_color=[0.10, 0.11, 0.14, 0.96],
            elevation=0,
            padding=[dp(12 * layout_scale), dp(8 * layout_scale), dp(12 * layout_scale), dp(8 * layout_scale)],
        )
        row = MDBoxLayout(orientation="horizontal", spacing=dp(8 * layout_scale))
        meta = MDBoxLayout(orientation="vertical", spacing=dp(2 * layout_scale))
        meta.add_widget(
            MDLabel(
                text=self._friendly_title(tx),
                theme_text_color="Custom",
                text_color=[0.95, 0.95, 0.95, 1],
                bold=True,
                font_size=f"{15 * text_scale:.1f}sp",
            )
        )
        meta.add_widget(
            MDLabel(
                text=self._friendly_time(str(tx.get("timestamp", "") or "")),
                theme_text_color="Custom",
                text_color=[0.74, 0.76, 0.80, 1],
                font_style="Body",
                font_size=f"{11.5 * text_scale:.1f}sp",
            )
        )
        if detail_text:
            meta.add_widget(
                MDLabel(
                    text=detail_text,
                    theme_text_color="Custom",
                    text_color=[0.74, 0.76, 0.80, 1],
                    font_style="Body",
                    font_size=f"{10.5 * text_scale:.1f}sp",
                )
            )
        amount_label = MDLabel(
            text=f"{sign} GHS {abs(amount):,.2f}",
            halign="right",
            theme_text_color="Custom",
            text_color=amount_color,
            bold=True,
            font_size=f"{14.5 * text_scale:.1f}sp",
        )

        row.add_widget(meta)
        row.add_widget(amount_label)
        card.add_widget(row)
        return card

    def load_transactions(self):
        self._set_feedback("Refreshing transactions...", "info")
        ok, payload = self._request("GET", "/wallet/transactions/me", params={"limit": 50})
        container = self.ids.tx_list
        container.clear_widgets()

        if ok and isinstance(payload, list):
            self.summary_text = f"{len(payload)} item(s)"
            if not payload:
                empty_card = MDCard(
                    size_hint_y=None,
                    height=dp(64 * float(self.layout_scale or 1.0)),
                    radius=[dp(14 * float(self.layout_scale or 1.0))],
                    md_bg_color=[0.10, 0.11, 0.14, 0.96],
                    padding=[
                        dp(12 * float(self.layout_scale or 1.0)),
                        dp(8 * float(self.layout_scale or 1.0)),
                        dp(12 * float(self.layout_scale or 1.0)),
                        dp(8 * float(self.layout_scale or 1.0)),
                    ],
                    elevation=0,
                )
                empty_card.add_widget(
                    MDLabel(
                        text="No transactions found yet.",
                        halign="center",
                        theme_text_color="Custom",
                        text_color=[0.74, 0.76, 0.80, 1],
                    )
                )
                container.add_widget(empty_card)
                self._set_feedback("No transactions yet.", "warning")
                return

            for tx in payload[:50]:
                container.add_widget(self._build_item(tx))
            self._set_feedback("Transactions loaded.", "success")
            return

        detail = self._extract_detail(payload) or "Unable to fetch transactions."
        self.summary_text = "Sync failed"
        self._set_feedback(detail, "error")
        self._show_popup("Transaction Sync Error", detail)


Builder.load_string(KV)
