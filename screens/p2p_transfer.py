from kivy.lang import Builder
from kivy.properties import StringProperty

from core.screen_actions import ActionScreen
from core.popup_manager import show_confirm_dialog
from utils.network import normalize_ghana_number

MIN_P2P_TRANSFER_GHS = 1.0
P2P_TRANSFER_FEE_RATE = 0.005
P2P_DAILY_FREE_LIMIT_GHS = 100.0

KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp
#:set BG (0.03, 0.04, 0.06, 1)
#:set SURFACE (0.08, 0.10, 0.14, 0.95)
#:set SURFACE_SOFT (0.12, 0.14, 0.18, 0.95)
#:set GREEN_CARD (0.24, 0.43, 0.34, 0.96)
#:set GOLD (0.94, 0.79, 0.46, 1)
#:set GOLD_SOFT (0.93, 0.77, 0.39, 1)
#:set TEXT_MAIN (0.95, 0.95, 0.95, 1)
#:set TEXT_SUB (0.74, 0.76, 0.80, 1)
<P2PTransferScreen>:
    MDBoxLayout:
        orientation: "vertical"

        canvas.before:
            Color:
                rgba: BG
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
                padding: [dp(16 * root.layout_scale), dp(16 * root.layout_scale), dp(16 * root.layout_scale), dp(18 * root.layout_scale)]
                spacing: dp(10 * root.layout_scale)

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(52 * root.layout_scale)

                    MDLabel:
                        text: "P2P Transfer"
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

                MDLabel:
                    text: root.page_subtitle
                    theme_text_color: "Custom"
                    text_color: TEXT_SUB
                    font_size: sp(12.5 * root.text_scale)
                    adaptive_height: True

                MDCard:
                    radius: [dp(22 * root.layout_scale)]
                    md_bg_color: GREEN_CARD
                    elevation: 0
                    size_hint_y: None
                    height: dp(134 * root.layout_scale)
                    padding: [dp(14 * root.layout_scale)] * 4

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(4 * root.layout_scale)

                        MDLabel:
                            text: "Available Balance"
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN

                        MDLabel:
                            text: root.balance_display
                            font_style: "Headline"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: GOLD
                            font_size: sp(28 * root.text_scale)

                        MDLabel:
                            text: root.wallet_status
                            theme_text_color: "Custom"
                            text_color: 0.80, 0.92, 0.80, 1
                            font_size: sp(12 * root.text_scale)

                MDCard:
                    radius: [dp(20 * root.layout_scale)]
                    md_bg_color: SURFACE_SOFT
                    elevation: 0
                    padding: [dp(14 * root.layout_scale)] * 4
                    adaptive_height: True

                    MDBoxLayout:
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: dp(8 * root.layout_scale)

                        MDLabel:
                            text: "Send Money Securely"
                            theme_text_color: "Custom"
                            text_color: GOLD
                            bold: True

                        MDLabel:
                            text: "Transfer to any valid registered Cyber Cash user number. Minimum amount is GHS 1.00. Enjoy free P2P transfers up to GHS 100.00 per day; a 0.5% fee applies only on amounts above your daily free limit."
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(12 * root.text_scale)
                            adaptive_height: True

                        MDLabel:
                            text: root.fee_status_text
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                        MDLabel:
                            text: "Recipient Number"
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            bold: True
                            adaptive_height: True

                        MDTextField:
                            id: recipient_input
                            hint_text: "Recipient number, e.g. 0241234567"
                            mode: "outlined"

                        MDLabel:
                            text: "Amount to Send"
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            bold: True
                            adaptive_height: True

                        MDTextField:
                            id: amount_input
                            hint_text: "Amount to send"
                            mode: "outlined"
                            input_filter: "float"
                            on_text: root.update_transfer_preview(self.text)

                        MDLabel:
                            text: root.transfer_preview
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                        MDLabel:
                            text: "Total debit comes from your wallet balance: amount plus any applicable fee."
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                        MDFillRoundFlatIconButton:
                            text: "Send Funds"
                            icon: "send"
                            md_bg_color: GOLD_SOFT
                            text_color: BG
                            size_hint_y: None
                            height: dp(52 * root.layout_scale)
                            on_release: root.send_funds()

                MDGridLayout:
                    cols: 1 if root.compact_mode else 2
                    spacing: dp(8 * root.layout_scale)
                    adaptive_height: True
                    size_hint_y: None
                    height: self.minimum_height

                    MDRaisedButton:
                        text: "Refresh"
                        size_hint_y: None
                        height: dp(48 * root.layout_scale)
                        on_release: root.load_wallet()

                    MDRaisedButton:
                        text: "History"
                        size_hint_y: None
                        height: dp(48 * root.layout_scale)
                        on_release:
                            if root.manager: root.manager.current = "transactions"

                MDLabel:
                    text: root.feedback_text
                    size_hint_y: None
                    height: self.texture_size[1] if self.text else 0
                    theme_text_color: "Custom"
                    text_color: root.feedback_color

                MDLabel:
                    text: root.feedback_hint if root.feedback_text else ""
                    size_hint_y: None
                    height: self.texture_size[1] if self.text else 0
                    theme_text_color: "Custom"
                    text_color: TEXT_SUB
                    font_size: sp(11.5 * root.text_scale)

                Widget:
                    size_hint_y: None
                    height: dp(8 * root.layout_scale)

        BottomNavBar:
            nav_variant: "send"
            active_target: "p2p_transfer"
            layout_scale: root.layout_scale
            text_scale: root.text_scale
            icon_scale: root.icon_scale
            bar_color: SURFACE
"""


class P2PTransferScreen(ActionScreen):
    page_subtitle = StringProperty("Send funds from your wallet to another registered user and review the fee before you confirm.")
    balance_display = StringProperty("GHS 0.00")
    wallet_status = StringProperty("Pulling live wallet...")
    transfer_preview = StringProperty("Minimum transfer is GHS 1.00. First GHS 100.00 per day is free; fee applies only above this.")
    fee_status_text = StringProperty("Today's free remaining: loading...")
    feedback_hint = StringProperty("")

    def on_pre_enter(self):
        self.load_wallet()
        self.load_fee_status()
        amount_field = self.ids.get("amount_input")
        self.update_transfer_preview(amount_field.text if amount_field is not None else "")

    @staticmethod
    def _parse_amount(raw_amount: str) -> float:
        try:
            return float(str(raw_amount or "").strip())
        except Exception:
            return 0.0

    def update_transfer_preview(self, raw_amount: str) -> None:
        amount = self._parse_amount(raw_amount)
        if amount < MIN_P2P_TRANSFER_GHS:
            self.transfer_preview = "Minimum transfer is GHS 1.00. First GHS 100.00 per day is free; fee applies only above this."
            return

        free_remaining = float(getattr(self, "_p2p_free_remaining", P2P_DAILY_FREE_LIMIT_GHS) or 0.0)
        feeable_amount = max(0.0, round(amount - free_remaining, 2))
        fee = round(feeable_amount * P2P_TRANSFER_FEE_RATE, 2)
        total = round(amount + fee, 2)
        if fee <= 0:
            self.transfer_preview = (
                f"Recipient gets GHS {amount:,.2f}. "
                f"Fee: GHS 0.00 (within daily free limit). "
                f"Total debit: GHS {total:,.2f}."
            )
            return

        self.transfer_preview = (
            f"Recipient gets GHS {amount:,.2f}. "
            f"Feeable: GHS {feeable_amount:,.2f} @ 0.5%. "
            f"Fee: GHS {fee:,.2f}. "
            f"Total debit: GHS {total:,.2f}."
        )

    def load_fee_status(self, notify: bool = False) -> None:
        ok, payload = self._request("GET", "/wallet/p2p/fee-status")
        if ok and isinstance(payload, dict):
            free_limit = float(payload.get("p2p_daily_free_limit", P2P_DAILY_FREE_LIMIT_GHS) or 0.0) or P2P_DAILY_FREE_LIMIT_GHS
            total_sent = float(payload.get("p2p_total_sent_today", 0.0) or 0.0)
            free_remaining = float(payload.get("p2p_free_remaining", free_limit) or 0.0)
            setattr(self, "_p2p_free_limit", free_limit)
            setattr(self, "_p2p_total_sent_today", total_sent)
            setattr(self, "_p2p_free_remaining", free_remaining)
            self.fee_status_text = f"Today's free remaining: GHS {free_remaining:,.2f} of {free_limit:,.2f}"
            if notify:
                self._set_feedback("Daily fee status updated.", "success")
                self.feedback_hint = "Transfers within your daily free limit have zero fee."
            return

        detail = self._extract_detail(payload) or "Unable to load fee status."
        setattr(self, "_p2p_free_limit", P2P_DAILY_FREE_LIMIT_GHS)
        setattr(self, "_p2p_total_sent_today", 0.0)
        setattr(self, "_p2p_free_remaining", P2P_DAILY_FREE_LIMIT_GHS)
        self.fee_status_text = "Today's free remaining: unavailable (using default GHS 100.00)"
        if notify:
            self._set_feedback(detail, "warning")
            self.feedback_hint = "Fee preview may be approximate until the server is reachable."

    def load_wallet(self, notify: bool = False):
        ok, payload = self._request("GET", "/wallet/me")
        if ok and isinstance(payload, dict):
            balance = float(payload.get("balance", 0.0) or 0.0)
            self.balance_display = f"GHS {balance:,.2f}"
            self.wallet_status = "Live wallet balance"
            if notify:
                self._set_feedback("Wallet updated.", "success")
                self.feedback_hint = "Confirm the recipient number and review the fee preview before sending."
            return

        detail = self._extract_detail(payload) or "Unable to load wallet."
        self.wallet_status = "Wallet sync unavailable"
        self._set_feedback(detail, "error")
        self.feedback_hint = "Check your connection and refresh the wallet balance before sending funds."
        self._show_popup("Wallet Sync Error", detail)

    @staticmethod
    def _friendly_transfer_error(detail: str) -> str:
        message = str(detail or "").strip()
        normalized = message.lower()
        if "recipient user not found" in normalized:
            return "Recipient not found. Please use a valid registered user number."
        if "recipient_wallet_id" in normalized and "valid 10-digit registered number" in normalized:
            return "Enter a valid 10-digit registered number."
        if "recipient_wallet_id" in normalized and "required" in normalized:
            return "Recipient registered number is required."
        if "minimum p2p transfer amount is ghs 1.00" in normalized:
            return "Minimum P2P transfer amount is GHS 1.00."
        if "cannot transfer funds to yourself" in normalized:
            return "You cannot send funds to your own number. Please enter another recipient."
        if "insufficient balance" in normalized:
            return "Insufficient balance. Make sure the amount plus any applicable fee is available."
        return message or "Unable to complete transfer right now."

    def send_funds(self):
        recipient = normalize_ghana_number(self.ids.recipient_input.text.strip())
        amount = self._parse_amount(self.ids.amount_input.text)

        if not recipient or len(recipient) != 10:
            self._set_feedback("Enter a valid 10-digit registered number.", "error")
            self.feedback_hint = "Use the recipient's registered Ghana number, for example 0241234567."
            self._show_popup(
                "Invalid Recipient",
                "Please enter a valid 10-digit Ghana registered number.",
            )
            return

        if amount < MIN_P2P_TRANSFER_GHS:
            self._set_feedback("Enter an amount from GHS 1.00 or more.", "error")
            self.feedback_hint = "Example: 10 means you are sending GHS 10 before the transfer fee is added."
            self._show_popup("Invalid Amount", "Minimum P2P transfer amount is GHS 1.00.")
            return

        self.load_fee_status()
        free_remaining = float(getattr(self, "_p2p_free_remaining", P2P_DAILY_FREE_LIMIT_GHS) or 0.0)
        feeable_amount = max(0.0, round(amount - free_remaining, 2))
        estimated_fee = round(feeable_amount * P2P_TRANSFER_FEE_RATE, 2)
        estimated_total = round(amount + estimated_fee, 2)

        def _do_transfer():
            self._set_feedback(
                (
                    f"Processing transfer... Amount: GHS {amount:,.2f}, "
                    f"Estimated fee: GHS {estimated_fee:,.2f}, "
                    f"Total debit: GHS {estimated_total:,.2f}."
                ),
                "info",
            )
            self.feedback_hint = "Keep this screen open while the transfer is being processed."

            ok, payload = self._request(
                "POST",
                "/wallet/transfer",
                payload={
                    "recipient_wallet_id": recipient,
                    "amount": amount,
                    "currency": "GHS",
                    "source_balance": "balance",
                    "recipient_must_be_agent": False,
                },
            )

            if ok and isinstance(payload, dict):
                ref = str(payload.get("transfer_reference", "")).strip()
                charged_fee = float(payload.get("transfer_fee", estimated_fee) or 0.0)
                total_debited = float(payload.get("total_debited", estimated_total) or 0.0)
                fee_free_amount = float(payload.get("p2p_fee_free_amount", 0.0) or 0.0)
                feeable_amount_actual = float(payload.get("p2p_feeable_amount", 0.0) or 0.0)

                if charged_fee <= 0:
                    fee_line = "Fee: GHS 0.00 (daily free limit applied)"
                else:
                    fee_line = f"Fee (0.5% on GHS {feeable_amount_actual:,.2f}): GHS {charged_fee:,.2f}"

                message = (
                    f"Transfer successful to {recipient}.\n"
                    f"Amount: GHS {amount:,.2f}\n"
                    f"Free today: GHS {fee_free_amount:,.2f}\n"
                    f"{fee_line}\n"
                    f"Total debited: GHS {total_debited:,.2f}"
                )
                if ref:
                    message = f"{message}\nRef: {ref}"

                self._set_feedback(message, "success")
                self.feedback_hint = "The form has been cleared. You can send another transfer or check transaction history."
                self._show_popup("P2P Transfer Successful", message)
                self.ids.recipient_input.text = ""
                self.ids.amount_input.text = ""
                self.update_transfer_preview("")
                self.load_wallet()
                self.load_fee_status()
                return

            detail = self._extract_detail(payload)
            friendly = self._friendly_transfer_error(detail)
            self._set_feedback(friendly, "error")
            self.feedback_hint = "Check the recipient number, amount, and wallet balance, then try again."
            self._show_popup("Transfer Failed", friendly)

        confirm_message = (
            f"Send to: {recipient}\n"
            f"Amount: GHS {amount:,.2f}\n"
            f"Free remaining today: GHS {free_remaining:,.2f}\n"
            f"Feeable amount: GHS {feeable_amount:,.2f}\n"
            f"Estimated fee (0.5%): GHS {estimated_fee:,.2f}\n"
            f"Total debit: GHS {estimated_total:,.2f}\n\n"
            "Transfers are free up to GHS 100.00 per day. Fees apply only above this limit."
        )
        show_confirm_dialog(
            self,
            title="Confirm P2P Transfer",
            message=confirm_message,
            on_confirm=_do_transfer,
            confirm_label="Send",
            cancel_label="Cancel",
        )


Builder.load_string(KV)
