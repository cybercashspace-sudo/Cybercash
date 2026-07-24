import json
import threading

from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.utils import get_color_from_hex
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDIconButton, MDRaisedButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDIcon, MDLabel
from kivymd.uix.textfield import MDTextField

try:
    from kivymd.uix.appbar import MDTopAppBar
except ImportError:  # pragma: no cover - older KivyMD fallback
    from kivymd.uix.toolbar import MDToolbar as MDTopAppBar

from core.bottom_nav import BottomNavBar
from core.popup_manager import show_confirm_dialog, show_message_dialog
from core.screen_actions import ActionScreen


KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp

#:set BG (0.04, 0.05, 0.07, 1)
#:set SURFACE (0.09, 0.11, 0.15, 0.96)
#:set SURFACE_SOFT (0.12, 0.14, 0.19, 0.96)
#:set CARD_BLUE (0.09, 0.21, 0.43, 1)
#:set GOLD (0.94, 0.79, 0.46, 1)
#:set GOLD_SOFT (0.92, 0.74, 0.35, 1)
#:set TEXT_MAIN (0.96, 0.96, 0.98, 1)
#:set TEXT_SUB (0.74, 0.76, 0.80, 1)
#:set SUCCESS (0.54, 0.82, 0.67, 1)
#:set WARNING (0.94, 0.79, 0.46, 1)
#:set DANGER (0.96, 0.47, 0.42, 1)

<VirtualCardScreen>:
    MDBoxLayout:
        orientation: "vertical"
        md_bg_color: BG

        MDTopAppBar:
            title: "Virtual Card"
            anchor_title: "center"
            elevation: 0
            md_bg_color: BG
            specific_text_color: GOLD
            left_action_items: [["arrow-left", lambda x: root.go_back()]]
            right_action_items: [["refresh", lambda x: root.refresh_data()]]

        ScrollView:
            do_scroll_x: False
            bar_width: 0

            MDBoxLayout:
                orientation: "vertical"
                adaptive_height: True
                spacing: dp(18 * root.layout_scale)
                padding: [dp(16 * root.layout_scale), dp(12 * root.layout_scale), dp(16 * root.layout_scale), dp(28 * root.layout_scale)]

                MDCard:
                    size_hint_y: None
                    height: dp(250 * root.layout_scale)
                    radius: [dp(28)]
                    elevation: 0
                    md_bg_color: CARD_BLUE
                    padding: dp(20 * root.layout_scale)

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(10 * root.layout_scale)

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(28 * root.layout_scale)

                            MDLabel:
                                text: "CYBER CASH"
                                theme_text_color: "Custom"
                                text_color: GOLD
                                bold: True
                                font_size: sp(14 * root.text_scale)

                            MDLabel:
                                text: "VISA"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                bold: True
                                halign: "right"
                                font_size: sp(22 * root.text_scale)

                        MDLabel:
                            text: root.card_number_display
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            bold: True
                            font_size: sp(26 * root.text_scale)
                            halign: "center"
                            size_hint_y: None
                            height: dp(36 * root.layout_scale)

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(18 * root.layout_scale)

                            MDLabel:
                                text: "CARD HOLDER"
                                theme_text_color: "Custom"
                                text_color: [1, 1, 1, 0.62]
                                font_size: sp(10 * root.text_scale)

                            MDLabel:
                                text: "EXPIRES"
                                theme_text_color: "Custom"
                                text_color: [1, 1, 1, 0.62]
                                font_size: sp(10 * root.text_scale)
                                halign: "right"

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(24 * root.layout_scale)

                            MDLabel:
                                text: root.cardholder
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                bold: True
                                font_size: sp(16 * root.text_scale)

                            MDLabel:
                                text: root.expiry
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                bold: True
                                font_size: sp(16 * root.text_scale)
                                halign: "right"

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(18 * root.layout_scale)

                            MDLabel:
                                text: root.card_status
                                theme_text_color: "Custom"
                                text_color: SUCCESS if root.card_status == "Active" else WARNING if root.card_status == "Frozen" else TEXT_SUB
                                font_size: sp(12 * root.text_scale)

                            MDLabel:
                                text: root.card_currency
                                theme_text_color: "Custom"
                                text_color: [1, 1, 1, 0.7]
                                font_size: sp(12 * root.text_scale)
                                halign: "right"

                GridLayout:
                    cols: 2
                    size_hint_y: None
                    height: self.minimum_height
                    spacing: dp(12 * root.layout_scale)

                    MDCard:
                        size_hint_y: None
                        height: dp(74 * root.layout_scale)
                        radius: [dp(20)]
                        md_bg_color: SURFACE
                        elevation: 0
                        on_release: root.toggle_details()
                        opacity: 1
                        disabled: not bool(root.card_id)

                        MDBoxLayout:
                            padding: dp(12)
                            spacing: dp(10)

                            MDIcon:
                                icon: "eye-outline" if not root.details_visible else "eye-off-outline"
                                theme_text_color: "Custom"
                                text_color: GOLD
                                pos_hint: {"center_y": .5}

                            MDLabel:
                                text: "Show Details" if not root.details_visible else "Hide Details"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_size: sp(13 * root.text_scale)

                    MDCard:
                        size_hint_y: None
                        height: dp(74 * root.layout_scale)
                        radius: [dp(20)]
                        md_bg_color: SURFACE
                        elevation: 0
                        on_release: root.copy_card_number()
                        disabled: not bool(root.card_id and root._raw_number)

                        MDBoxLayout:
                            padding: dp(12)
                            spacing: dp(10)

                            MDIcon:
                                icon: "content-copy"
                                theme_text_color: "Custom"
                                text_color: GOLD
                                pos_hint: {"center_y": .5}

                            MDLabel:
                                text: "Copy Number"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_size: sp(13 * root.text_scale)

                    MDCard:
                        size_hint_y: None
                        height: dp(74 * root.layout_scale)
                        radius: [dp(20)]
                        md_bg_color: SURFACE
                        elevation: 0
                        on_release: root.toggle_freeze()
                        disabled: not bool(root.card_id)

                        MDBoxLayout:
                            padding: dp(12)
                            spacing: dp(10)

                            MDIcon:
                                icon: "snowflake" if not root.is_frozen else "fire"
                                theme_text_color: "Custom"
                                text_color: GOLD
                                pos_hint: {"center_y": .5}

                            MDLabel:
                                text: "Freeze Card" if not root.is_frozen else "Unfreeze Card"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_size: sp(13 * root.text_scale)

                    MDCard:
                        size_hint_y: None
                        height: dp(74 * root.layout_scale)
                        radius: [dp(20)]
                        md_bg_color: SURFACE
                        elevation: 0
                        on_release: root.replace_card_flow()
                        disabled: not bool(root.card_id)

                        MDBoxLayout:
                            padding: dp(12)
                            spacing: dp(10)

                            MDIcon:
                                icon: "credit-card-refresh-outline"
                                theme_text_color: "Custom"
                                text_color: GOLD
                                pos_hint: {"center_y": .5}

                            MDLabel:
                                text: "Replace Card"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_size: sp(13 * root.text_scale)

                MDCard:
                    radius: [dp(24)]
                    md_bg_color: SURFACE_SOFT
                    elevation: 0
                    padding: dp(18 * root.layout_scale)
                    size_hint_y: None
                    height: info_panel.height + dp(36 * root.layout_scale)

                    MDBoxLayout:
                        id: info_panel
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: dp(12 * root.layout_scale)

                        MDLabel:
                            text: "Card Info"
                            theme_text_color: "Custom"
                            text_color: GOLD
                            bold: True
                            font_size: sp(18 * root.text_scale)
                            size_hint_y: None
                            height: dp(24 * root.layout_scale)

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(52 * root.layout_scale)

                            MDBoxLayout:
                                orientation: "vertical"

                                MDLabel:
                                    text: "Card Balance"
                                    theme_text_color: "Custom"
                                    text_color: TEXT_SUB
                                    font_size: sp(11 * root.text_scale)
                                    size_hint_y: None
                                    height: dp(15)

                                MDLabel:
                                    text: root.card_balance_display
                                    theme_text_color: "Custom"
                                    text_color: TEXT_MAIN
                                    bold: True
                                    font_size: sp(19 * root.text_scale)

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(52 * root.layout_scale)

                            MDBoxLayout:
                                orientation: "vertical"

                                MDLabel:
                                    text: "Status"
                                    theme_text_color: "Custom"
                                    text_color: TEXT_SUB
                                    font_size: sp(11 * root.text_scale)
                                    size_hint_y: None
                                    height: dp(15)

                                MDLabel:
                                    text: root.card_status
                                    theme_text_color: "Custom"
                                    text_color: SUCCESS if root.card_status == "Active" else WARNING if root.card_status == "Frozen" else TEXT_MAIN
                                    bold: True
                                    font_size: sp(19 * root.text_scale)

                        MDBoxLayout:
                            orientation: "vertical"
                            adaptive_height: True

                            MDLabel:
                                text: "CVV"
                                theme_text_color: "Custom"
                                text_color: TEXT_SUB
                                font_size: sp(11 * root.text_scale)
                                size_hint_y: None
                                height: dp(15)

                            MDLabel:
                                text: root.cvv
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                bold: True
                                font_size: sp(19 * root.text_scale)

                            MDLabel:
                                text: "The CVV stays hidden unless the card provider exposes it securely."
                                theme_text_color: "Custom"
                                text_color: [1, 1, 1, 0.55]
                                font_size: sp(10 * root.text_scale)
                                size_hint_y: None
                                height: self.texture_size[1] if self.text else 0

                MDCard:
                    radius: [dp(24)]
                    md_bg_color: SURFACE_SOFT
                    elevation: 0
                    padding: dp(18 * root.layout_scale)
                    size_hint_y: None
                    height: load_panel.height + dp(36 * root.layout_scale)

                    MDBoxLayout:
                        id: load_panel
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: dp(12 * root.layout_scale)

                        MDLabel:
                            text: "Load Card"
                            theme_text_color: "Custom"
                            text_color: GOLD
                            bold: True
                            font_size: sp(18 * root.text_scale)
                            size_hint_y: None
                            height: dp(24 * root.layout_scale)

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(24 * root.layout_scale)

                            MDLabel:
                                text: "Wallet Balance"
                                theme_text_color: "Custom"
                                text_color: TEXT_SUB
                                font_size: sp(11 * root.text_scale)

                            MDLabel:
                                text: root.wallet_balance_display
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                bold: True
                                font_size: sp(13 * root.text_scale)
                                halign: "right"

                        MDTextField:
                            id: load_amount
                            hint_text: "Amount to load"
                            helper_text: "This amount is loaded from your wallet into the card."
                            helper_text_mode: "on_focus"
                            mode: "fill"
                            input_filter: "float"
                            size_hint_y: None
                            height: dp(72 * root.layout_scale)
                            disabled: root.processing or root.is_frozen or not bool(root.card_id)

                        MDRaisedButton:
                            text: "Load Card"
                            size_hint_x: 1
                            size_hint_y: None
                            height: dp(52 * root.layout_scale)
                            md_bg_color: GOLD
                            text_color: BG
                            disabled: root.processing or root.is_frozen or not bool(root.card_id)
                            on_release: root.submit_load()

                        MDLabel:
                            text: root.wallet_status
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11 * root.text_scale)
                            size_hint_y: None
                            height: self.texture_size[1] if self.text else 0

                MDCard:
                    radius: [dp(24)]
                    md_bg_color: SURFACE_SOFT
                    elevation: 0
                    padding: dp(18 * root.layout_scale)
                    size_hint_y: None
                    height: transaction_panel.height + dp(36 * root.layout_scale)

                    MDBoxLayout:
                        id: transaction_panel
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: dp(12 * root.layout_scale)

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(24 * root.layout_scale)

                            MDLabel:
                                text: "Recent Transactions"
                                theme_text_color: "Custom"
                                text_color: GOLD
                                bold: True
                                font_size: sp(18 * root.text_scale)

                            MDIconButton:
                                icon: "refresh"
                                theme_text_color: "Custom"
                                text_color: GOLD
                                on_release: root.load_card_transactions()

                        MDBoxLayout:
                            id: transaction_list
                            orientation: "vertical"
                            adaptive_height: True
                            spacing: dp(10 * root.layout_scale)

                MDLabel:
                    text: root.feedback_text
                    theme_text_color: "Custom"
                    text_color: root.feedback_color
                    font_size: sp(12 * root.text_scale)
                    size_hint_y: None
                    height: self.texture_size[1] if self.text else 0

        BottomNavBar:
            nav_variant: "default"
            active_target: "virtual_card"
            layout_scale: root.layout_scale
            text_scale: root.text_scale
            icon_scale: root.icon_scale
            bar_color: app.ui_surface
            active_color: app.gold
            inactive_color: app.ui_text_secondary
"""


class VirtualCardScreen(ActionScreen):
    name = StringProperty("virtual_card")
    card_number_display = StringProperty("**** **** **** ****")
    cardholder = StringProperty("Loading...")
    expiry = StringProperty("--/--")
    cvv = StringProperty("***")
    card_balance_display = StringProperty("USD 0.00")
    wallet_balance_display = StringProperty("GHS 0.00")
    wallet_status = StringProperty("Wallet not verified yet")
    card_status = StringProperty("No card")
    card_currency = StringProperty("USD")
    wallet_currency = StringProperty("GHS")
    details_visible = BooleanProperty(False)
    is_frozen = BooleanProperty(False)
    card_loaded = BooleanProperty(False)
    processing = BooleanProperty(False)
    card_id = NumericProperty(0)

    _raw_number = ""
    _raw_cvv = ""
    _wallet_balance_val = 0.0

    @staticmethod
    def _normalize_status(status_value) -> str:
        status = str(status_value or "").strip().lower()
        if status == "frozen":
            return "blocked"
        return status

    @staticmethod
    def _mask_card_number(card_number: str) -> str:
        digits = "".join(ch for ch in str(card_number or "") if ch.isdigit())
        if len(digits) < 4:
            return "**** **** **** ****"
        return f"**** **** **** {digits[-4:]}"

    @staticmethod
    def _parse_metadata(raw_metadata: str | None) -> dict:
        if not raw_metadata:
            return {}
        try:
            parsed = json.loads(raw_metadata)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def _select_card_record(self, payload):
        if isinstance(payload, dict):
            return payload
        if not isinstance(payload, list) or not payload:
            return None

        for record in payload:
            if self._normalize_status(record.get("status")) in {"active", "blocked"}:
                return record
        return payload[0]

    def _apply_empty_card_state(self):
        self.card_id = 0
        self._raw_number = ""
        self._raw_cvv = ""
        self.card_number_display = "**** **** **** ****"
        self.cardholder = "No Active Card"
        self.expiry = "--/--"
        self.cvv = "***"
        self.card_balance_display = f"{self.card_currency} 0.00"
        self.card_status = "No card"
        self.is_frozen = False

    def _sync_sensitive_fields(self):
        if self.details_visible and self._raw_number:
            self.card_number_display = self._raw_number
        else:
            self.card_number_display = self._mask_card_number(self._raw_number)

        if self.details_visible:
            self.cvv = self._raw_cvv if self._raw_cvv else "Securely stored"
        else:
            self.cvv = "***"

    def _apply_card_payload(self, payload: dict):
        app = MDApp.get_running_app()
        self.card_id = int(payload.get("id") or 0)
        self._raw_number = str(payload.get("card_number") or "")
        self._raw_cvv = str(payload.get("cvv") or payload.get("cvv_plaintext") or payload.get("cvv_value") or "")
        self.card_currency = str(payload.get("currency") or "USD")
        self.cardholder = str(payload.get("card_holder") or getattr(app, "user_name", "") or "Cyber Cash User")
        self.expiry = str(payload.get("expiry_date") or payload.get("expiry") or "--/--")

        status = self._normalize_status(payload.get("status"))
        self.is_frozen = status == "blocked"
        if status == "active":
            self.card_status = "Active"
        elif status == "blocked":
            self.card_status = "Frozen"
        elif status:
            self.card_status = status.title()
        else:
            self.card_status = "Unknown"

        balance = float(payload.get("balance") or 0.0)
        self.card_balance_display = f"{self.card_currency} {balance:,.2f}"
        self._sync_sensitive_fields()

    def on_pre_enter(self):
        if not self.card_loaded:
            self.refresh_data()
            self.card_loaded = True

    def refresh_data(self):
        self._set_feedback("Syncing card data...", "info")
        self.load_card_data()
        self.load_wallet()
        self.verify_wallet_integrity()
        self.load_card_transactions()

    def load_card_data(self):
        ok, payload = self._request("GET", "/virtualcards/me")
        card = self._select_card_record(payload) if ok else None
        if card:
            self._apply_card_payload(card)
            self._set_feedback("Virtual card synced.", "success")
            return

        self._apply_empty_card_state()
        self._set_feedback("No virtual card found for this account.", "warning")

    def load_wallet(self):
        ok, payload = self._request("GET", "/wallet/me")
        if ok and isinstance(payload, dict):
            self.wallet_currency = str(payload.get("currency") or "GHS")
            self._wallet_balance_val = float(payload.get("balance") or 0.0)
            self.wallet_balance_display = f"{self.wallet_currency} {self._wallet_balance_val:,.2f}"
            return

        self.wallet_balance_display = f"{self.wallet_currency} 0.00"

    def verify_wallet_integrity(self):
        ok, payload = self._request("GET", "/wallet/verify")
        if not ok or not isinstance(payload, dict):
            self.wallet_status = "Wallet verification unavailable"
            return

        status = str(payload.get("status") or "").lower()
        wallet_balance = float(payload.get("wallet_balance") or self._wallet_balance_val or 0.0)
        ledger_balance = float(payload.get("ledger_balance") or wallet_balance)
        difference = float(payload.get("difference") or (wallet_balance - ledger_balance))

        if status == "verified":
            self.wallet_status = "Wallet verified against the ledger"
            self._wallet_balance_val = wallet_balance
        elif status == "mismatch":
            self.wallet_status = f"Ledger mismatch: {difference:+.2f}"
            self._set_feedback(
                f"Wallet mismatch detected. Ledger balance is {self.wallet_currency} {ledger_balance:,.2f}.",
                "warning",
            )
        else:
            self.wallet_status = str(payload.get("error") or "Wallet verification unavailable")

    def load_card_transactions(self):
        if not self.card_id:
            self._render_transactions([])
            return

        ok, payload = self._request("GET", f"/virtualcards/{int(self.card_id)}/transactions")
        if ok and isinstance(payload, list):
            self._render_transactions(payload)
            return

        self._render_transactions([])

    def _format_transaction_amount(self, tx_type: str, amount: float, currency: str) -> tuple[str, list[float]]:
        normalized = str(tx_type or "").strip().upper()
        amount = abs(float(amount or 0.0))
        if normalized == "CARD_LOAD":
            return f"+{currency} {amount:,.2f}", [0.54, 0.82, 0.67, 1]
        if normalized in {"CARD_SPEND", "VIRTUAL_CARD_ISSUANCE_FEE"}:
            return f"-{currency} {amount:,.2f}", [0.96, 0.47, 0.42, 1]
        if normalized == "CARD_WITHDRAW":
            return f"+{currency} {amount:,.2f}", [0.54, 0.82, 0.67, 1]
        return f"{currency} {amount:,.2f}", [0.95, 0.95, 0.95, 1]

    def _render_transactions(self, items):
        container = self.ids.transaction_list
        container.clear_widgets()

        if not items:
            container.add_widget(
                MDLabel(
                    text="No recent card transactions found.",
                    theme_text_color="Secondary",
                    halign="center",
                    font_size=sp(14 * self.text_scale),
                    adaptive_height=True,
                    padding=[0, dp(20)],
                )
            )
            return

        for item in items[:10]:
            metadata = self._parse_metadata(item.get("metadata_json"))
            tx_type = str(item.get("type") or "").strip()
            title = str(
                metadata.get("merchant_name")
                or metadata.get("merchant")
                or tx_type.replace("_", " ").title()
            )
            subtitle = str(item.get("timestamp") or "").replace("T", " ")
            amount_text, amount_color = self._format_transaction_amount(
                tx_type,
                float(item.get("amount") or 0.0),
                str(item.get("currency") or self.card_currency or "USD"),
            )

            card = MDCard(
                adaptive_height=True,
                md_bg_color=[1, 1, 1, 0.03],
                radius=[16],
                padding=dp(16),
                elevation=0,
            )
            row = MDBoxLayout(orientation="horizontal", spacing=dp(12), adaptive_height=True)
            left = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(2))
            left.add_widget(
                MDLabel(
                    text=title,
                    theme_text_color="Custom",
                    text_color=[1, 1, 1, 0.92],
                    bold=True,
                    font_size=sp(14 * self.text_scale),
                )
            )
            left.add_widget(
                MDLabel(
                    text=subtitle[:19] if subtitle else "Recent activity",
                    theme_text_color="Custom",
                    text_color=[1, 1, 1, 0.56],
                    font_size=sp(11 * self.text_scale),
                )
            )
            row.add_widget(left)
            row.add_widget(
                MDLabel(
                    text=amount_text,
                    halign="right",
                    bold=True,
                    theme_text_color="Custom",
                    text_color=amount_color,
                    font_size=sp(14 * self.text_scale),
                )
            )
            card.add_widget(row)
            container.add_widget(card)

    def toggle_details(self):
        self.details_visible = not self.details_visible
        self._sync_sensitive_fields()
        if self.details_visible:
            if self._raw_cvv:
                self.show_cvv_popup()
            else:
                self._set_feedback("Card number revealed. CVV stays hidden by design.", "info")

    def show_cvv_popup(self):
        if self._raw_cvv:
            message = f"Your Card CVV is: [b]{self._raw_cvv}[/b]\n\nKeep it private and only use it where you trust the merchant."
        else:
            message = "CVV is securely stored and cannot be re-shown from this screen."

        show_message_dialog(
            self,
            title="Security Reveal",
            message=message,
            close_label="I Understand",
        )

    def copy_card_number(self):
        if self._raw_number:
            Clipboard.copy(self._raw_number)
            self._set_feedback("Card number copied to clipboard", "success")
        else:
            self._set_feedback("No card number available to copy", "warning")

    def download_statement(self):
        if not self.card_id:
            self._set_feedback("Load a card before downloading a statement.", "warning")
            return

        self._set_feedback("Fetching statement URL...", "info")
        ok, payload = self._request("GET", f"/virtualcards/{int(self.card_id)}/statement")
        if ok and isinstance(payload, dict) and payload.get("url"):
            import webbrowser

            webbrowser.open(payload["url"])
            self._set_feedback("Statement opened in browser", "success")
            return

        self._set_feedback("Statement service is currently unavailable.", "warning")

    def replace_card_flow(self):
        if not self.card_id:
            self._set_feedback("Load a card before requesting a reissue.", "warning")
            return

        show_confirm_dialog(
            self,
            title="Replace Virtual Card?",
            message="Your current card number will be reissued in place. The card balance stays intact and the card stays tied to this account.",
            confirm_label="Replace Card",
            on_confirm=self._perform_replace,
        )

    def _perform_replace(self):
        if not self.card_id:
            self._set_feedback("No card available to replace.", "warning")
            return

        self._set_feedback("Processing card replacement...", "info")
        ok, payload = self._request("POST", f"/virtualcards/{int(self.card_id)}/replace")
        if ok:
            self._set_feedback("Card replaced successfully", "success")
            self.refresh_data()
            return

        detail = self._extract_detail(payload) or "Failed to replace card"
        self._set_feedback(detail, "error")

    def toggle_freeze(self):
        if not self.card_id:
            self._set_feedback("Load a card before freezing it.", "warning")
            return

        new_state = not self.is_frozen
        status_value = "blocked" if new_state else "active"
        self._set_feedback(f"Updating card to {status_value}...", "info")

        ok, payload = self._request(
            "PATCH",
            f"/virtualcards/{int(self.card_id)}/status",
            payload={"status": status_value},
        )
        if ok:
            returned_status = self._normalize_status((payload or {}).get("status") if isinstance(payload, dict) else status_value)
            self.is_frozen = returned_status == "blocked"
            self.card_status = "Frozen" if self.is_frozen else "Active"
            self._set_feedback(f"Card is now {self.card_status}", "success")
            return

        self._set_feedback(self._extract_detail(payload) or "Failed to update card status", "error")

    def submit_load(self):
        if self.processing:
            return
        if not self.card_id:
            self._set_feedback("Load a card before adding funds.", "warning")
            return
        if self.is_frozen:
            self._set_feedback("Unfreeze the card before loading funds.", "warning")
            return

        raw_amt = self.ids.load_amount.text
        try:
            amount = float(raw_amt)
        except ValueError:
            self._set_feedback("Please enter a valid amount", "error")
            return

        if amount <= 0:
            self._set_feedback("Amount must be greater than zero", "error")
            return

        if amount > self._wallet_balance_val:
            self._set_feedback("Insufficient wallet balance", "error")
            return

        self.processing = True
        self._set_feedback("Processing card load...", "info")

        def _worker():
            ok, payload = self._request(
                "POST",
                f"/virtualcards/{int(self.card_id)}/load",
                payload={"amount": amount},
            )
            Clock.schedule_once(lambda dt: self._on_load_complete(ok, payload))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_load_complete(self, ok, payload):
        self.processing = False
        if ok:
            self._set_feedback("Card loaded successfully!", "success")
            self.ids.load_amount.text = ""
            self.refresh_data()
            show_message_dialog(self, title="Success", message="Your virtual card has been credited.")
            return

        detail = self._extract_detail(payload) or "Failed to load card"
        self._set_feedback(detail, "error")


Builder.load_string(KV)
