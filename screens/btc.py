import json
import threading
from datetime import datetime, timezone

import requests

from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.properties import ColorProperty, StringProperty
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel

from core.message_sanitizer import sanitize_backend_message
from core.popup_manager import show_confirm_dialog
from core.screen_actions import ActionScreen


KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp
#:set BG (0.043, 0.059, 0.078, 1)
#:set BG_SOFT (0.055, 0.074, 0.096, 1)
#:set CARD (0.075, 0.096, 0.126, 0.98)
#:set CARD2 (0.085, 0.114, 0.142, 0.98)
#:set GOLD (0.831, 0.686, 0.216, 1)
#:set GOLD_SOFT (0.93, 0.77, 0.39, 1)
#:set GREEN (0.122, 0.239, 0.169, 1)
#:set SURFACE (0.118, 0.146, 0.176, 0.98)
#:set TEXT_MAIN (0.96, 0.97, 0.98, 1)
#:set TEXT_SUB (0.69, 0.73, 0.78, 1)
<BTCScreen>:
    MDBoxLayout:
        orientation: "vertical"

        canvas.before:
            Color:
                rgba: BG
            Rectangle:
                pos: self.pos
                size: self.size
            Color:
                rgba: 0.40, 0.31, 0.15, 0.10
            Ellipse:
                pos: self.x + self.width * 0.16, self.y + self.height * 0.74
                size: self.width * 0.58, self.width * 0.58
            Color:
                rgba: 0.25, 0.39, 0.31, 0.18
            Ellipse:
                pos: self.x + self.width * 0.32, self.y + self.height * 0.42
                size: self.width * 0.72, self.width * 0.72
            Color:
                rgba: BG_SOFT
            RoundedRectangle:
                pos: self.x - dp(20), self.y + dp(32)
                size: self.width + dp(40), self.height * 0.64
                radius: [dp(40), dp(40), dp(18), dp(18)]

        ScrollView:
            do_scroll_x: False
            bar_width: 0

            MDBoxLayout:
                orientation: "vertical"
                size_hint_y: None
                height: self.minimum_height
                size_hint_x: None
                width: min((self.parent.width if self.parent else root.width), dp(720))
                pos_hint: {"center_x": 0.5}
                padding: [dp(16 * root.layout_scale), dp(16 * root.layout_scale), dp(16 * root.layout_scale), dp(18 * root.layout_scale)]
                spacing: dp(12 * root.layout_scale)

                MDCard:
                    radius: [dp(24 * root.layout_scale)]
                    md_bg_color: CARD
                    line_color: (0.27, 0.23, 0.14, 0.45)
                    elevation: 0
                    padding: dp(18 * root.layout_scale)
                    size_hint_y: None
                    height: self.minimum_height

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(10 * root.layout_scale)
                        adaptive_height: True

                        MDBoxLayout:
                            orientation: "vertical" if root.width < dp(600) else "horizontal"
                            size_hint_y: None
                            height: self.minimum_height
                            spacing: dp(12 * root.layout_scale)

                            MDBoxLayout:
                                orientation: "vertical"
                                spacing: dp(2 * root.layout_scale)
                                adaptive_height: True
                                size_hint_x: 1

                                MDLabel:
                                    text: "BTC Wallet"
                                    font_style: "Title"
                                    bold: True
                                    theme_text_color: "Custom"
                                    text_color: GOLD
                                    adaptive_height: True

                                MDLabel:
                                    text: "Live price, address, sends."
                                    text_size: self.width, None
                                    halign: "left"
                                    adaptive_height: True
                                    theme_text_color: "Custom"
                                    text_color: TEXT_SUB
                                    font_size: sp(12 * root.text_scale)

                            MDBoxLayout:
                                orientation: "horizontal" if root.width < dp(600) else "vertical"
                                size_hint_x: 1 if root.width < dp(600) else None
                                width: dp(118 * root.layout_scale)
                                spacing: dp(6 * root.layout_scale)

                                MDCard:
                                    size_hint_y: None
                                    height: dp(30 * root.layout_scale)
                                    radius: [dp(15 * root.layout_scale)]
                                    md_bg_color: (0.09, 0.18, 0.12, 0.96)
                                    line_color: (0.20, 0.35, 0.24, 0.55)
                                    elevation: 0
                                    padding: [dp(8 * root.layout_scale), 0, dp(8 * root.layout_scale), 0]

                                    MDLabel:
                                        text: root.market_status_text
                                        halign: "center"
                                        valign: "middle"
                                        text_size: self.size
                                        bold: True
                                        theme_text_color: "Custom"
                                        text_color: root.market_status_color
                                        font_size: sp(10.5 * root.text_scale)

                                MDTextButton:
                                    text: "Back"
                                    theme_text_color: "Custom"
                                    text_color: GOLD
                                    on_release: root.go_back()

                        MDLabel:
                            text: root.wallet_state_text
                            text_size: self.width, None
                            halign: "left"
                            adaptive_height: True
                            theme_text_color: "Custom"
                            text_color: root.wallet_state_color
                            font_size: sp(12 * root.text_scale)

                MDGridLayout:
                    cols: 1 if root.width < dp(600) else 2
                    spacing: dp(10 * root.layout_scale)
                    adaptive_height: True
                    size_hint_y: None
                    height: self.minimum_height

                    MDCard:
                        radius: [dp(22 * root.layout_scale)]
                        md_bg_color: CARD2
                        line_color: (0.27, 0.23, 0.14, 0.45)
                        elevation: 0
                        padding: dp(16 * root.layout_scale)
                        size_hint_y: None
                        height: self.minimum_height

                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(6 * root.layout_scale)
                            adaptive_height: True

                            MDLabel:
                                text: "Balance"
                                bold: True
                                theme_text_color: "Custom"
                                text_color: GOLD
                                font_size: sp(16 * root.text_scale)
                                adaptive_height: True

                            MDLabel:
                                text: root.btc_balance_display
                                font_style: "Headline"
                                bold: True
                                theme_text_color: "Custom"
                                text_color: GOLD
                                font_size: sp(28 * root.text_scale)
                                adaptive_height: True

                            MDLabel:
                                text: root.fiat_balance_display
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_size: sp(13 * root.text_scale)
                                adaptive_height: True

                    MDCard:
                        radius: [dp(22 * root.layout_scale)]
                        md_bg_color: CARD2
                        line_color: (0.27, 0.23, 0.14, 0.45)
                        elevation: 0
                        padding: dp(16 * root.layout_scale)
                        size_hint_y: None
                        height: self.minimum_height

                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(6 * root.layout_scale)
                            adaptive_height: True

                            MDLabel:
                                text: "Live BTC Price"
                                bold: True
                                theme_text_color: "Custom"
                                text_color: GOLD
                                font_size: sp(16 * root.text_scale)
                                adaptive_height: True

                            MDLabel:
                                text: root.btc_price_display
                                font_style: "Headline"
                                bold: True
                                theme_text_color: "Custom"
                                text_color: GOLD
                                font_size: sp(28 * root.text_scale)
                                adaptive_height: True

                            MDLabel:
                                text: root.btc_change_display
                                theme_text_color: "Custom"
                                text_color: root.btc_change_color
                                font_size: sp(13 * root.text_scale)
                                adaptive_height: True

                            MDLabel:
                                text: root.network_fee_display
                                theme_text_color: "Custom"
                                text_color: TEXT_SUB
                                font_size: sp(11.5 * root.text_scale)
                                adaptive_height: True

                            MDLabel:
                                text: root.market_last_updated_text
                                theme_text_color: "Custom"
                                text_color: TEXT_SUB
                                font_size: sp(10.5 * root.text_scale)
                                adaptive_height: True

                MDCard:
                    radius: [dp(22 * root.layout_scale)]
                    md_bg_color: CARD2
                    line_color: (0.27, 0.23, 0.14, 0.45)
                    elevation: 0
                    padding: dp(16 * root.layout_scale)
                    size_hint_y: None
                    height: self.minimum_height

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(10 * root.layout_scale)
                        adaptive_height: True

                        MDLabel:
                            text: "Receive BTC"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: GOLD
                            font_size: sp(16 * root.text_scale)
                            adaptive_height: True

                        MDLabel:
                            text: "Generate or copy your BTC address."
                            text_size: self.width, None
                            halign: "left"
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                        MDLabel:
                            text: root.btc_address
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            font_size: sp(12 * root.text_scale)
                            shorten: True
                            shorten_from: "center"
                            text_size: self.width, None
                            halign: "left"
                            adaptive_height: True

                        MDGridLayout:
                            cols: 1 if root.width < dp(480) else 2
                            spacing: dp(8 * root.layout_scale)
                            adaptive_height: True
                            size_hint_y: None
                            height: self.minimum_height

                            MDFillRoundFlatIconButton:
                                text: "Generate Address"
                                icon: "plus-circle-outline"
                                md_bg_color: GOLD_SOFT
                                text_color: BG
                                size_hint_y: None
                                height: dp(48 * root.layout_scale)
                                on_release: root.ensure_btc_wallet()

                            MDFillRoundFlatIconButton:
                                text: "Copy Address"
                                icon: "content-copy"
                                md_bg_color: SURFACE
                                text_color: TEXT_MAIN
                                size_hint_y: None
                                height: dp(48 * root.layout_scale)
                                on_release: root.copy_btc_address()

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(2 * root.layout_scale)

                MDGridLayout:
                    cols: 1 if root.width < dp(760) else 2
                    spacing: dp(10 * root.layout_scale)
                    adaptive_height: True
                    size_hint_y: None
                    height: self.minimum_height

                    MDCard:
                        radius: [dp(22 * root.layout_scale)]
                        md_bg_color: CARD2
                        line_color: (0.27, 0.23, 0.14, 0.45)
                        elevation: 0
                        padding: dp(16 * root.layout_scale)
                        size_hint_y: None
                        height: self.minimum_height
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(10 * root.layout_scale)
                            adaptive_height: True

                            MDLabel:
                                text: "Send BTC"
                                bold: True
                                theme_text_color: "Custom"
                                text_color: GOLD
                                font_size: sp(16 * root.text_scale)
                                adaptive_height: True

                            MDLabel:
                                text: "Send BTC."
                                text_size: self.width, None
                                halign: "left"
                                theme_text_color: "Custom"
                                text_color: TEXT_SUB
                                font_size: sp(11.5 * root.text_scale)
                                adaptive_height: True

                            MDTextField:
                                id: send_address_input
                                hint_text: "BTC address"
                                helper_text: "Address only."
                                helper_text_mode: "on_focus"
                                mode: "filled"
                                theme_bg_color: "Custom"
                                fill_color_normal: 0.11, 0.14, 0.17, 1
                                fill_color_focus: 0.13, 0.16, 0.20, 1
                                theme_line_color: "Custom"
                                line_color_normal: 0.22, 0.30, 0.24, 0.65
                                line_color_focus: GOLD
                                text_color_normal: TEXT_MAIN
                                text_color_focus: TEXT_MAIN
                                font_size: sp(13 * root.text_scale)
                                multiline: False

                            MDTextField:
                                id: send_amount_input
                                hint_text: "Amount (BTC)"
                                helper_text: "Fee shown below."
                                helper_text_mode: "on_focus"
                                mode: "filled"
                                theme_bg_color: "Custom"
                                fill_color_normal: 0.11, 0.14, 0.17, 1
                                fill_color_focus: 0.13, 0.16, 0.20, 1
                                theme_line_color: "Custom"
                                line_color_normal: 0.22, 0.30, 0.24, 0.65
                                line_color_focus: GOLD
                                text_color_normal: TEXT_MAIN
                                text_color_focus: TEXT_MAIN
                                font_size: sp(13 * root.text_scale)
                                input_filter: "float"
                                multiline: False

                            MDFillRoundFlatIconButton:
                                text: "Send BTC"
                                icon: "send"
                                md_bg_color: GREEN
                                text_color: BG
                                size_hint_y: None
                                height: dp(48 * root.layout_scale)
                                on_release: root.confirm_send_btc()

                    MDCard:
                        radius: [dp(22 * root.layout_scale)]
                        md_bg_color: CARD2
                        line_color: (0.27, 0.23, 0.14, 0.45)
                        elevation: 0
                        padding: dp(16 * root.layout_scale)
                        size_hint_y: None
                        height: self.minimum_height
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(10 * root.layout_scale)
                            adaptive_height: True

                            MDLabel:
                                text: "Conversion Preview"
                                bold: True
                                theme_text_color: "Custom"
                                text_color: GOLD
                                font_size: sp(16 * root.text_scale)
                                adaptive_height: True

                            MDLabel:
                                text: "See BTC in GHS."
                                text_size: self.width, None
                                halign: "left"
                                theme_text_color: "Custom"
                                text_color: TEXT_SUB
                                font_size: sp(11.5 * root.text_scale)
                                adaptive_height: True

                            MDTextField:
                                id: convert_amount_input
                                hint_text: "Amount (BTC)"
                                helper_text: "Live price."
                                helper_text_mode: "on_focus"
                                mode: "filled"
                                theme_bg_color: "Custom"
                                fill_color_normal: 0.11, 0.14, 0.17, 1
                                fill_color_focus: 0.13, 0.16, 0.20, 1
                                theme_line_color: "Custom"
                                line_color_normal: 0.22, 0.30, 0.24, 0.65
                                line_color_focus: GOLD
                                text_color_normal: TEXT_MAIN
                                text_color_focus: TEXT_MAIN
                                font_size: sp(13 * root.text_scale)
                                input_filter: "float"
                                multiline: False
                                on_text: root.update_conversion_preview()

                            MDLabel:
                                text: root.convert_preview_text
                                theme_text_color: "Custom"
                                text_color: root.convert_preview_color
                                font_size: sp(12 * root.text_scale)
                                adaptive_height: True

                            MDFillRoundFlatIconButton:
                                text: "Preview Value"
                                icon: "swap-horizontal"
                                md_bg_color: GOLD
                                text_color: BG
                                size_hint_y: None
                                height: dp(48 * root.layout_scale)
                                on_release: root.update_conversion_preview()

                MDCard:
                    radius: [dp(22 * root.layout_scale)]
                    md_bg_color: CARD2
                    line_color: (0.27, 0.23, 0.14, 0.45)
                    elevation: 0
                    padding: dp(16 * root.layout_scale)
                    size_hint_y: None
                    height: self.minimum_height

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(10 * root.layout_scale)
                        adaptive_height: True

                        MDBoxLayout:
                            orientation: "horizontal"
                            size_hint_y: None
                            height: dp(34 * root.layout_scale)
                            spacing: dp(8 * root.layout_scale)

                            MDLabel:
                                text: "Recent Activity"
                                bold: True
                                theme_text_color: "Custom"
                                text_color: GOLD
                                font_size: sp(16 * root.text_scale)
                                adaptive_height: True

                            Widget:

                            MDTextButton:
                                text: "Refresh"
                                theme_text_color: "Custom"
                                text_color: GOLD
                                font_size: sp(12 * root.text_scale)
                                on_release: root.load_btc_data(True)

                        MDLabel:
                            text: root.transaction_summary
                            text_size: self.width, None
                            halign: "left"
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11 * root.text_scale)
                            adaptive_height: True

                        MDBoxLayout:
                            id: btc_activity_list
                            orientation: "vertical"
                            adaptive_height: True
                            spacing: dp(8 * root.layout_scale)

                MDLabel:
                    text: root.feedback_text
                    text_size: self.width, None
                    halign: "left"
                    adaptive_height: True
                    theme_text_color: "Custom"
                    text_color: root.feedback_color
                    font_size: sp(12 * root.text_scale)

                Widget:
                    size_hint_y: None
                    height: dp(8 * root.layout_scale)

        BottomNavBar:
            nav_variant: "btc"
            active_target: "btc"
            layout_scale: root.layout_scale
            text_scale: root.text_scale
            icon_scale: root.icon_scale
"""


class BTCScreen(ActionScreen):
    supported_coins_text = StringProperty("Bitcoin")
    btc_balance_display = StringProperty("0.00000000 BTC")
    fiat_balance_display = StringProperty("~ GHS 0.00")
    btc_price_display = StringProperty("BTC/USDT $0.00")
    btc_change_display = StringProperty("+0.00% 24h")
    market_high_low_display = StringProperty("24h: $0.00 / $0.00")
    market_last_updated_text = StringProperty("Updating...")
    network_fee_display = StringProperty("Fee ~0.00005 BTC | Min 0.0001 BTC")
    btc_address = StringProperty("No BTC address yet.")
    wallet_state_text = StringProperty("Preparing wallet...")
    wallet_state_color = ColorProperty([0.74, 0.76, 0.80, 1])
    market_status_text = StringProperty("MARKET LIVE")
    market_status_color = ColorProperty([0.54, 0.82, 0.67, 1])
    btc_change_color = ColorProperty([0.54, 0.82, 0.67, 1])
    transaction_summary = StringProperty("Loading activity...")
    convert_preview_text = StringProperty("Enter BTC to preview GHS.")
    convert_preview_color = ColorProperty([0.74, 0.76, 0.80, 1])

    def on_pre_enter(self):
        self.load_btc_data()

    def on_size(self, *args):
        super().on_size(*args)
        if getattr(self, "_btc_transactions", None) is not None:
            Clock.schedule_once(self._refresh_transaction_cards, 0)

    def _refresh_transaction_cards(self, *_args) -> None:
        transactions = getattr(self, "_btc_transactions", None)
        if transactions is None or "btc_activity_list" not in self.ids:
            return
        self._render_transactions(list(transactions))

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
    def _format_btc(amount: object) -> str:
        try:
            value = float(amount or 0.0)
        except Exception:
            value = 0.0
        return f"{value:,.8f}"

    @staticmethod
    def _format_usd(amount: object) -> str:
        try:
            value = float(amount or 0.0)
        except Exception:
            value = 0.0
        return f"${value:,.2f}"

    @staticmethod
    def _truncate_hash(value: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            return "Awaiting blockchain hash"
        if len(raw) <= 18:
            return raw
        return f"{raw[:10]}...{raw[-6:]}"

    @staticmethod
    def _parse_json(value: object) -> dict:
        raw = str(value or "").strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _extract_confirmations(tx: dict) -> int | None:
        metadata = BTCScreen._parse_json(tx.get("metadata_json"))
        confirmations = metadata.get("confirmations")
        try:
            if confirmations is None:
                return None
            return int(confirmations)
        except Exception:
            return None

    def _set_wallet_state(self, message: str, level: str = "info") -> None:
        palette = {
            "info": [0.74, 0.76, 0.80, 1],
            "success": [0.54, 0.82, 0.67, 1],
            "warning": [0.94, 0.79, 0.46, 1],
            "error": [0.96, 0.47, 0.42, 1],
        }
        self.wallet_state_text = str(message or "").strip()
        self.wallet_state_color = palette.get(level, palette["info"])

    def _set_text(self, name: str, value, default: str = "") -> None:
        widget = self.ids.get(name)
        if widget is None:
            return
        widget.text = default if value is None else str(value)

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

    def _build_transaction_card(self, tx: dict) -> MDCard:
        layout_scale = float(self.layout_scale or 1.0)
        text_scale = float(self.text_scale or 1.0)
        tx_type = str(tx.get("type", "") or "").strip().lower()
        status_raw = str(tx.get("status", "") or "pending").strip().lower()
        amount = self._format_btc(tx.get("amount", 0.0))
        hash_text = self._truncate_hash(str(tx.get("transaction_hash", "") or ""))
        created_text = self._friendly_time(str(tx.get("created_at", "") or ""))
        confirmations = self._extract_confirmations(tx)
        narrow_layout = bool((float(self.width or 0.0) < dp(480)) or self.compact_mode)

        if tx_type == "deposit":
            direction_label = "Incoming BTC"
            indicator_color = [0.18, 0.30, 0.24, 0.96]
            amount_color = [0.54, 0.82, 0.67, 1]
            arrow_text = "IN"
        elif tx_type == "withdrawal":
            direction_label = "Outgoing BTC"
            indicator_color = [0.31, 0.16, 0.16, 0.96]
            amount_color = [0.96, 0.47, 0.42, 1]
            arrow_text = "OUT"
        else:
            direction_label = "BTC Activity"
            indicator_color = [0.18, 0.22, 0.28, 0.96]
            amount_color = [0.94, 0.79, 0.46, 1]
            arrow_text = "TX"

        status_label = status_raw.replace("_", " ").title() or "Pending"
        if status_raw == "confirmed":
            status_color = [0.54, 0.82, 0.67, 1]
        elif status_raw in {"failed", "rejected"}:
            status_color = [0.96, 0.47, 0.42, 1]
        else:
            status_color = [0.94, 0.79, 0.46, 1]

        card = MDCard(
            size_hint_y=None,
            height=dp((160 if narrow_layout else 104) * layout_scale),
            radius=[dp(16 * layout_scale)],
            md_bg_color=[0.10, 0.12, 0.15, 0.96],
            line_color=[0.24, 0.28, 0.24, 0.42],
            elevation=0,
            padding=[dp(12 * layout_scale), dp(10 * layout_scale), dp(12 * layout_scale), dp(10 * layout_scale)],
        )

        def _make_indicator(size_dp: float) -> MDCard:
            indicator = MDCard(
                size_hint=(None, None),
                size=(dp(size_dp * layout_scale), dp(size_dp * layout_scale)),
                radius=[dp(12 * layout_scale)],
                md_bg_color=indicator_color,
                line_color=indicator_color,
                elevation=0,
            )
            indicator.add_widget(
                MDLabel(
                    text=arrow_text,
                    halign="center",
                    valign="middle",
                    text_size=indicator.size,
                    theme_text_color="Custom",
                    text_color=[1, 1, 1, 1],
                    font_size=f"{13.5 * text_scale:.1f}sp",
                    bold=True,
                )
            )
            return indicator

        if narrow_layout:
            content = MDBoxLayout(
                orientation="vertical",
                spacing=dp(8 * layout_scale),
                adaptive_height=True,
            )

            top_row = MDBoxLayout(
                orientation="horizontal",
                spacing=dp(10 * layout_scale),
                size_hint_y=None,
                height=dp(48 * layout_scale),
            )
            top_row.add_widget(_make_indicator(40))

            title_box = MDBoxLayout(orientation="vertical", spacing=dp(2 * layout_scale), adaptive_height=True)
            title_box.add_widget(
                MDLabel(
                    text=direction_label,
                    theme_text_color="Custom",
                    text_color=[0.96, 0.97, 0.98, 1],
                    bold=True,
                    font_size=f"{14.5 * text_scale:.1f}sp",
                    size_hint_y=None,
                    height=dp(20 * layout_scale),
                )
            )
            title_box.add_widget(
                MDLabel(
                    text=f"{created_text} | {status_label}",
                    theme_text_color="Custom",
                    text_color=[0.72, 0.76, 0.81, 1],
                    font_size=f"{11 * text_scale:.1f}sp",
                    size_hint_y=None,
                    height=dp(18 * layout_scale),
                )
            )
            top_row.add_widget(title_box)
            content.add_widget(top_row)

            details = MDBoxLayout(orientation="vertical", spacing=dp(2 * layout_scale), adaptive_height=True)
            details.add_widget(
                MDLabel(
                    text=f"Hash: {hash_text}",
                    theme_text_color="Custom",
                    text_color=[0.72, 0.76, 0.81, 1],
                    font_size=f"{10.5 * text_scale:.1f}sp",
                    size_hint_y=None,
                    height=dp(18 * layout_scale),
                )
            )
            if confirmations is not None:
                details.add_widget(
                    MDLabel(
                        text=f"Confirmations: {confirmations}",
                        theme_text_color="Custom",
                        text_color=[0.72, 0.76, 0.81, 1],
                        font_size=f"{10.5 * text_scale:.1f}sp",
                        size_hint_y=None,
                        height=dp(18 * layout_scale),
                    )
                )
            content.add_widget(details)

            amount_box = MDBoxLayout(orientation="vertical", spacing=dp(2 * layout_scale), adaptive_height=True)
            amount_box.add_widget(
                MDLabel(
                    text=f"{amount} BTC",
                    halign="right",
                    theme_text_color="Custom",
                    text_color=amount_color,
                    bold=True,
                    font_size=f"{15 * text_scale:.1f}sp",
                )
            )
            amount_box.add_widget(
                MDLabel(
                    text=status_label,
                    halign="right",
                    theme_text_color="Custom",
                    text_color=status_color,
                    font_size=f"{11 * text_scale:.1f}sp",
                )
            )
            content.add_widget(amount_box)
            card.add_widget(content)
            return card

        row = MDBoxLayout(orientation="horizontal", spacing=dp(10 * layout_scale))
        row.add_widget(_make_indicator(44))

        meta = MDBoxLayout(orientation="vertical", spacing=dp(2 * layout_scale))
        meta.add_widget(
            MDLabel(
                text=direction_label,
                theme_text_color="Custom",
                text_color=[0.96, 0.97, 0.98, 1],
                bold=True,
                font_size=f"{14.5 * text_scale:.1f}sp",
                size_hint_y=None,
                height=dp(22 * layout_scale),
            )
        )
        meta.add_widget(
            MDLabel(
                text=f"{created_text} | {status_label}",
                theme_text_color="Custom",
                text_color=[0.72, 0.76, 0.81, 1],
                font_size=f"{11 * text_scale:.1f}sp",
                size_hint_y=None,
                height=dp(18 * layout_scale),
            )
        )
        meta.add_widget(
            MDLabel(
                text=f"Hash: {hash_text}",
                theme_text_color="Custom",
                text_color=[0.72, 0.76, 0.81, 1],
                font_size=f"{10.5 * text_scale:.1f}sp",
                size_hint_y=None,
                height=dp(18 * layout_scale),
            )
        )
        if confirmations is not None:
            meta.add_widget(
                MDLabel(
                    text=f"Confirmations: {confirmations}",
                    theme_text_color="Custom",
                    text_color=[0.72, 0.76, 0.81, 1],
                    font_size=f"{10.5 * text_scale:.1f}sp",
                    size_hint_y=None,
                    height=dp(18 * layout_scale),
                )
            )

        amount_box = MDBoxLayout(
            orientation="vertical",
            size_hint_x=None,
            width=dp(118 * layout_scale),
            spacing=dp(2 * layout_scale),
        )
        amount_box.add_widget(
            MDLabel(
                text=f"{amount} BTC",
                halign="right",
                theme_text_color="Custom",
                text_color=amount_color,
                bold=True,
                font_size=f"{14.5 * text_scale:.1f}sp",
            )
        )
        amount_box.add_widget(
            MDLabel(
                text=status_label,
                halign="right",
                theme_text_color="Custom",
                text_color=status_color,
                font_size=f"{11 * text_scale:.1f}sp",
            )
        )

        row.add_widget(meta)
        row.add_widget(amount_box)
        card.add_widget(row)
        return card

    def _render_transactions(self, transactions: list[dict]) -> None:
        container = self.ids.btc_activity_list
        container.clear_widgets()
        layout_scale = float(self.layout_scale or 1.0)
        if not transactions:
            empty_card = MDCard(
                size_hint_y=None,
                height=dp(72 * layout_scale),
                radius=[dp(14 * layout_scale)],
                md_bg_color=[0.10, 0.11, 0.14, 0.96],
                elevation=0,
                padding=[dp(12 * layout_scale)] * 4,
            )
            empty_card.add_widget(
                MDLabel(
                    text="No BTC activity yet. Create an address to receive BTC.",
                    halign="center",
                    theme_text_color="Custom",
                    text_color=[0.72, 0.76, 0.81, 1],
                    font_size=f"{11.5 * float(self.text_scale or 1.0):.1f}sp",
                )
            )
            container.add_widget(empty_card)
            return

        for tx in transactions[:5]:
            container.add_widget(self._build_transaction_card(tx))

    def _fetch_market_snapshot(self) -> dict:
        ok, payload = self._request("GET", "/crypto/market/btc", requires_auth=False)
        if ok and isinstance(payload, dict) and payload.get("last_price_usdt") is not None:
            return payload

        try:
            response = requests.get(
                "https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT",
                timeout=8,
            )
            response.raise_for_status()
            market = response.json()
            last_price = float(market.get("lastPrice") or market.get("price") or 0.0)
            return {
                "symbol": "BTCUSDT",
                "network": "Bitcoin",
                "min_deposit_btc": 0.0001,
                "withdrawal_fee_btc": 0.00005,
                "last_price_usdt": last_price,
                "price_change_percent_24h": float(market.get("priceChangePercent") or 0.0),
                "high_price_usdt": float(market.get("highPrice") or 0.0),
                "low_price_usdt": float(market.get("lowPrice") or 0.0),
                "volume_btc": float(market.get("volume") or 0.0),
                "usd_to_ghs_rate": 12.0,
                "estimated_ghs_per_btc": last_price * 12.0,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "source": "binance",
            }
        except Exception as exc:
            return {"error": sanitize_backend_message(exc, fallback="Unable to load BTC market data.")}

    def load_btc_data(self, notify: bool = False) -> None:
        if getattr(self, "_loading_btc", False):
            return
        self._loading_btc = True
        self._load_seq = int(getattr(self, "_load_seq", 0)) + 1
        seq = self._load_seq
        self._set_feedback("Syncing...", "info")
        threading.Thread(target=self._load_btc_data_worker, args=(seq, notify), daemon=True).start()

    def _load_btc_data_worker(self, seq: int, notify: bool) -> None:
        market_payload = self._fetch_market_snapshot()
        wallet_result = self._request("GET", "/crypto/wallets")
        tx_result = self._request("GET", "/crypto/transactions")
        Clock.schedule_once(lambda _dt: self._apply_loaded_data(seq, market_payload, wallet_result, tx_result, notify))

    def _apply_loaded_data(self, seq: int, market_payload, wallet_result, tx_result, notify: bool) -> None:
        if seq != int(getattr(self, "_load_seq", 0)):
            return
        self._loading_btc = False

        market_ok = isinstance(market_payload, dict) and not market_payload.get("error") and market_payload.get("last_price_usdt") is not None
        btc_balance = 0.0

        if market_ok:
            last_price = float(market_payload.get("last_price_usdt") or 0.0)
            change_percent = float(market_payload.get("price_change_percent_24h") or 0.0)
            high_price = float(market_payload.get("high_price_usdt") or 0.0)
            low_price = float(market_payload.get("low_price_usdt") or 0.0)
            estimated_ghs_per_btc = float(market_payload.get("estimated_ghs_per_btc") or (last_price * float(market_payload.get("usd_to_ghs_rate") or 12.0)))
            withdrawal_fee = float(market_payload.get("withdrawal_fee_btc") or 0.00005)
            min_deposit = float(market_payload.get("min_deposit_btc") or 0.0001)
            network = str(market_payload.get("network") or "Bitcoin")
            updated_at = str(market_payload.get("updated_at") or "")

            self.supported_coins_text = str(network)
            self.btc_price_display = f"BTC/USDT {self._format_usd(last_price)}"
            self.btc_change_display = f"{change_percent:+.2f}% 24h"
            self.btc_change_color = [0.54, 0.82, 0.67, 1] if change_percent >= 0 else [0.96, 0.47, 0.42, 1]
            self.market_high_low_display = f"24h: {self._format_usd(high_price)} / {self._format_usd(low_price)}"
            self.market_last_updated_text = f"Updated {self._friendly_time(updated_at)}"
            self.network_fee_display = f"Fee ~{withdrawal_fee:.5f} BTC | Min {min_deposit:.4f} BTC"
            self.market_status_text = "MARKET LIVE"
            self.market_status_color = [0.54, 0.82, 0.67, 1]
            self._estimated_ghs_per_btc = estimated_ghs_per_btc
        else:
            self.market_status_text = "MARKET UNAVAILABLE"
            self.market_status_color = [0.94, 0.79, 0.46, 1]
            self.market_last_updated_text = "Price feed unavailable."
            self.btc_price_display = "BTC/USDT $0.00"
            self.btc_change_display = "+0.00% 24h"
            self.btc_change_color = [0.74, 0.76, 0.80, 1]
            self.market_high_low_display = "24h: $0.00 / $0.00"
            self.network_fee_display = "Fee ~0.00005 BTC | Min 0.0001 BTC"
            self._estimated_ghs_per_btc = 0.0

        wallet_ok, wallet_payload = wallet_result
        btc_wallet = None
        if wallet_ok and isinstance(wallet_payload, list):
            for wallet in wallet_payload:
                if str(wallet.get("coin_type", "") or "").strip().upper() == "BTC":
                    btc_wallet = wallet
                    break

        if btc_wallet:
            btc_balance = float(btc_wallet.get("balance") or 0.0)
            self.btc_balance_display = f"{btc_balance:,.8f} BTC"
            self.btc_address = str(btc_wallet.get("address") or "").strip()
            self._set_wallet_state("Wallet ready.", "success")
        else:
            self.btc_balance_display = "0.00000000 BTC"
            self.btc_address = "No BTC address yet."
            self._set_wallet_state("No wallet yet. Generate one.", "warning")

        self.fiat_balance_display = (
            f"~ GHS {btc_balance * self._estimated_ghs_per_btc:,.2f}"
            if self._estimated_ghs_per_btc > 0
            else "~ GHS 0.00"
        )

        tx_ok, tx_payload = tx_result
        btc_transactions = []
        if tx_ok and isinstance(tx_payload, list):
            btc_transactions = [
                tx for tx in tx_payload
                if str(tx.get("coin_type", "") or "").strip().upper() == "BTC"
            ]
            btc_transactions.sort(key=lambda item: str(item.get("created_at", "") or ""), reverse=True)

        confirmed_count = sum(1 for tx in btc_transactions if str(tx.get("status", "") or "").strip().lower() == "confirmed")
        pending_count = sum(
            1 for tx in btc_transactions
            if str(tx.get("status", "") or "").strip().lower() in {"pending", "awaiting_confirmation"}
        )
        self._btc_transactions = list(btc_transactions)
        self.transaction_summary = (
            f"{len(btc_transactions)} BTC tx | {confirmed_count} confirmed | {pending_count} pending"
            if btc_transactions
            else "No BTC activity yet."
        )
        self._render_transactions(btc_transactions)

        if notify:
            self._set_feedback("Updated.", "success")

        if not market_ok and not wallet_ok and not tx_ok:
            detail = (
                self._extract_detail(market_payload)
                or self._extract_detail(wallet_payload)
                or self._extract_detail(tx_payload)
                or "Unable to load BTC data."
            )
            self._set_feedback(detail, "error")
        elif not market_ok:
            self._set_feedback(self._extract_detail(market_payload) or "Market unavailable.", "warning")

        self.update_conversion_preview()

    def focus_send_form(self) -> None:
        widget = self.ids.get("send_address_input")
        if widget is not None:
            widget.focus = True
        self._set_feedback("Fill address and amount.", "info")

    def focus_convert_form(self) -> None:
        widget = self.ids.get("convert_amount_input")
        if widget is not None:
            widget.focus = True
        self.update_conversion_preview()
        self._set_feedback("Preview BTC value.", "info")

    def update_conversion_preview(self) -> None:
        amount = self._read_float("convert_amount_input", 0.0)
        estimated_rate = float(getattr(self, "_estimated_ghs_per_btc", 0.0) or 0.0)
        if amount <= 0:
            self.convert_preview_text = "Enter BTC to preview GHS."
            self.convert_preview_color = [0.74, 0.76, 0.80, 1]
            return
        if estimated_rate <= 0:
            self.convert_preview_text = "Price unavailable."
            self.convert_preview_color = [0.94, 0.79, 0.46, 1]
            return
        estimated_value = amount * estimated_rate
        self.convert_preview_text = f"~ GHS {estimated_value:,.2f}"
        self.convert_preview_color = [0.54, 0.82, 0.67, 1]

    def ensure_btc_wallet(self) -> None:
        if getattr(self, "_loading_btc", False):
            return
        address = str(self.btc_address or "").strip()
        if address and not address.startswith("No BTC receive address"):
            Clipboard.copy(address)
            self._set_feedback("Address copied.", "success")
            return

        self._set_feedback("Generating address...", "info")
        ok, payload = self._request("POST", "/crypto/wallets", payload={"coin_type": "BTC"})
        if ok and isinstance(payload, dict):
            created_address = str(payload.get("address") or "").strip()
            if created_address:
                Clipboard.copy(created_address)
            self._set_feedback("Address generated.", "success")
            self.load_btc_data(True)
            return

        detail = self._extract_detail(payload) or "Unable to create BTC wallet."
        if "already has" in detail.lower():
            self._set_feedback("Wallet exists. Refreshing.", "warning")
            self.load_btc_data(True)
            return

        self._set_feedback(detail, "error")
        self._show_popup("BTC Wallet Error", detail)

    def copy_btc_address(self) -> None:
        address = str(self.btc_address or "").strip()
        if not address or address.startswith("No BTC receive address"):
            self._set_feedback("Create an address first.", "warning")
            return

        Clipboard.copy(address)
        self._set_feedback("Address copied.", "success")

    def receive_btc(self) -> None:
        address = str(self.btc_address or "").strip()
        if address and not address.startswith("No BTC receive address"):
            self.copy_btc_address()
            return
        self.ensure_btc_wallet()

    def confirm_send_btc(self) -> None:
        address = self._read_text("send_address_input", "")
        amount = self._read_float("send_amount_input", 0.0)
        if not address:
            self._set_feedback("Enter the address first.", "warning")
            return
        if amount <= 0:
            self._set_feedback("Enter a BTC amount.", "warning")
            return

        self._pending_btc_send = {"to_address": address, "amount": amount}
        fee_text = self.network_fee_display
        show_confirm_dialog(
            self,
            title="Confirm BTC Send",
            message=(
                f"Send {amount:,.8f} BTC to the destination address?\n\n"
                f"{fee_text}\n\n"
                "Double-check the address."
            ),
            confirm_label="Send BTC",
            cancel_label="Cancel",
            on_confirm=self.send_btc,
        )

    def send_btc(self) -> None:
        payload = getattr(self, "_pending_btc_send", None) or {}
        address = str(payload.get("to_address") or "").strip()
        amount = float(payload.get("amount") or 0.0)
        if not address or amount <= 0:
            self._set_feedback("Unable to send.", "error")
            return

        self._set_feedback("Sending...", "info")
        ok, response = self._request(
            "POST",
            "/crypto/withdraw",
            payload={"coin_type": "BTC", "to_address": address, "amount": amount},
        )
        if ok and isinstance(response, dict):
            status_text = str(response.get("status", "pending") or "pending").title()
            tx_hash = str(response.get("transaction_hash") or "").strip() or "Pending confirmation"
            self._set_feedback("Sent.", "success")
            self._show_popup(
                "BTC Withdrawal",
                f"Status: {status_text}\nHash: {tx_hash}",
            )
            self._set_text("send_address_input", "", "")
            self._set_text("send_amount_input", "", "")
            self.load_btc_data(True)
            return

        detail = self._extract_detail(response) or "Unable to send."
        self._set_feedback(detail, "error")
        self._show_popup("BTC Send Failed", detail)


Builder.load_string(KV)
