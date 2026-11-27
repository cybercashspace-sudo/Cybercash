import threading
import time
import uuid
import math
from kivy.clock import Clock
from kivy.lang import Builder
from kivymd.app import MDApp
from kivy.properties import BooleanProperty, StringProperty

from core.screen_actions import ActionScreen
from core.navigation import navigate
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

        PullRefreshScrollView:
            root_layout: root
            refresh_callback: root.pull_to_refresh
            spinner_color: app.gold
            circle_color: app.ui_background
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
                        text: "Send Money"
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
                            text: "GHS 100 daily free; 0.5% fee above the limit."
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

                        MDTextField:
                            id: recipient_input
                            hint_text: "Registered MoMo number"
                            mode: "rectangle"

                        MDTextField:
                            id: amount_input
                            hint_text: "Amount (GHS)"
                            mode: "rectangle"
                            input_filter: "float"
                            on_text: root.update_transfer_preview(self.text)

                        MDLabel:
                            text: root.transfer_preview
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                        MDFillRoundFlatIconButton:
                            text: root.transfer_button_text
                            icon: "send"
                            md_bg_color: GOLD_SOFT
                            text_color: BG
                            size_hint_y: None
                            height: dp(52 * root.layout_scale)
                            on_release: root.send_funds()
                            disabled: root.transfer_busy

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
                        on_release: root.load_wallet(notify=True)

                    MDRaisedButton:
                        text: "History"
                        size_hint_y: None
                        height: dp(48 * root.layout_scale)
                        on_release:
                            if root.manager: root.go_to_history()

                MDLabel:
                    text: root.feedback_text
                    size_hint_y: None
                    height: self.texture_size[1] if self.text else 0
                    theme_text_color: "Custom"
                    text_color: root.feedback_color

                Widget:
                    size_hint_y: None
                    height: dp(8 * root.layout_scale)

        BottomNavBar:
            nav_variant: "send"
            active_target: "p2p_transfer"
            layout_scale: root.layout_scale
            text_scale: root.text_scale
            icon_scale: root.icon_scale
            bar_color: app.ui_surface
            active_color: app.gold
            inactive_color: app.ui_text_secondary
"""


class P2PTransferScreen(ActionScreen):
    balance_display = StringProperty("GHS 0.00")
    wallet_status = StringProperty("Updating balance...")
    wallet_is_live = BooleanProperty(False)
    transfer_preview = StringProperty("Min GHS 1.00. GHS 100/day free; 0.5% above.")
    fee_status_text = StringProperty("Loading daily fee allowance...")
    transfer_busy = BooleanProperty(False)
    transfer_button_text = StringProperty("Review and send")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._wallet_loading = False
        self._fee_loading = False
        self._transfer_generation = 0
        self._transfer_submitting = False
        self._fee_loaded_at = 0.0
        self._pending_transfer = None
        self._transfer_idempotency_key = ""
        self._transfer_idempotency_fingerprint = None
        self._p2p_free_limit = P2P_DAILY_FREE_LIMIT_GHS
        self._p2p_total_sent_today = 0.0
        self._p2p_free_remaining = P2P_DAILY_FREE_LIMIT_GHS

    def on_pre_enter(self, *_args):
        self.load_wallet()
        self.load_fee_status()
        amount_field = self.ids.get("amount_input")
        self.update_transfer_preview(amount_field.text if amount_field is not None else "")

    def on_leave(self, *_args):
        if self.transfer_busy and not self._transfer_submitting:
            self._transfer_generation += 1
            self._pending_transfer = None
            self._release_transfer()
        parent_on_leave = getattr(super(), "on_leave", None)
        if callable(parent_on_leave):
            return parent_on_leave(*_args)

    @staticmethod
    def _parse_amount(raw_amount: str) -> float:
        try:
            return float(str(raw_amount or "").strip())
        except Exception:
            return 0.0

    @staticmethod
    def _number(value, fallback: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return float(fallback)
        return number if math.isfinite(number) and number >= 0 else float(fallback)

    def update_transfer_preview(self, raw_amount: str) -> None:
        amount = self._parse_amount(raw_amount)
        if amount < MIN_P2P_TRANSFER_GHS:
            self.transfer_preview = "Min GHS 1.00. GHS 100/day free; 0.5% above."
            return

        free_remaining = float(getattr(self, "_p2p_free_remaining", P2P_DAILY_FREE_LIMIT_GHS) or 0.0)
        feeable_amount = max(0.0, round(amount - free_remaining, 2))
        fee = round(feeable_amount * P2P_TRANSFER_FEE_RATE, 2)
        total = round(amount + fee, 2)
        self.transfer_preview = (
            f"Recipient gets GHS {amount:,.2f} | fee GHS {fee:,.2f} | total GHS {total:,.2f}"
        )

    def load_fee_status(self, notify: bool = False) -> None:
        if self._fee_loading:
            return
        self._fee_loading = True
        threading.Thread(
            target=self._load_fee_status_worker,
            args=(bool(notify),),
            daemon=True,
        ).start()

    def _load_fee_status_worker(self, notify: bool) -> None:
        try:
            ok, payload = self._request("GET", "/wallet/p2p/fee-status")
        except Exception:
            ok, payload = False, {"detail": "Fee status is unavailable. Check your connection."}
        Clock.schedule_once(lambda _dt: self._apply_fee_status(ok, payload, notify))

    def _apply_fee_status(self, ok: bool, payload: object, notify: bool = False) -> None:
        self._fee_loading = False
        pending = self._pending_transfer
        self._pending_transfer = None
        if ok and isinstance(payload, dict):
            free_limit = self._number(payload.get("p2p_daily_free_limit"), P2P_DAILY_FREE_LIMIT_GHS)
            if free_limit <= 0:
                free_limit = P2P_DAILY_FREE_LIMIT_GHS
            total_sent = self._number(payload.get("p2p_total_sent_today"), 0.0)
            free_remaining = self._number(payload.get("p2p_free_remaining"), max(0.0, free_limit - total_sent))
            self._p2p_free_limit = free_limit
            self._p2p_total_sent_today = total_sent
            self._p2p_free_remaining = min(free_limit, free_remaining)
            self._fee_loaded_at = time.monotonic()
            self.fee_status_text = f"Free today: GHS {self._p2p_free_remaining:,.2f}"
            amount_field = self.ids.get("amount_input")
            self.update_transfer_preview(amount_field.text if amount_field is not None else "")
            if pending is not None:
                recipient, amount, generation = pending
                if generation == self._transfer_generation and self._is_screen_active():
                    self._show_transfer_confirmation(recipient, amount, self._p2p_free_remaining, generation)
            elif notify:
                self._set_feedback("Fee allowance updated.", "success")
            return

        self._fee_loaded_at = 0.0
        self.fee_status_text = "Fee allowance unavailable."
        if pending is not None:
            _recipient, _amount, generation = pending
            if generation != self._transfer_generation:
                return
            self._release_transfer()
            if isinstance(payload, dict) and payload.get("_auth_required"):
                self._show_auth_required("Your session may have expired. Sign in again to continue.")
                return
            message = "Fee details are unavailable. Check your connection and try again."
            self._show_popup("Fee Details Unavailable", message)
            return
        if isinstance(payload, dict) and payload.get("_auth_required"):
            self._show_auth_required("Your session may have expired. Sign in again to continue.")
        elif notify:
            message = "Fee details are unavailable. Check your connection and try again."
            self._show_popup("Fee Details Unavailable", message)

    def load_wallet(self, notify: bool = False):
        if self._wallet_loading:
            return
        self._wallet_loading = True
        threading.Thread(
            target=self._load_wallet_worker,
            args=(bool(notify),),
            daemon=True,
        ).start()

    def _load_wallet_worker(self, notify: bool) -> None:
        try:
            ok, payload = self._request("GET", "/wallet/me", timeout=(4, 8))
        except Exception:
            ok, payload = False, {"detail": "Wallet balance is unavailable. Check your connection."}
        Clock.schedule_once(lambda _dt: self._apply_wallet_result(ok, payload, notify))

    def _apply_wallet_result(self, ok: bool, payload: object, notify: bool = False) -> None:
        self._wallet_loading = False
        if ok and isinstance(payload, dict) and "balance" in payload:
            raw_balance = payload.get("balance")
            try:
                balance = float(raw_balance)
            except (TypeError, ValueError):
                balance = float("nan")
            if not math.isfinite(balance) or balance < 0:
                ok = False
        if ok and isinstance(payload, dict) and "balance" in payload:
            self.balance_display = f"GHS {balance:,.2f}"
            self.wallet_status = "Live balance"
            self.wallet_is_live = True
            if notify:
                self._set_feedback("Balance updated.", "success")
            return

        self.wallet_is_live = False
        self.wallet_status = "Balance unavailable · Tap Refresh"
        if isinstance(payload, dict) and payload.get("_auth_required"):
            self.wallet_status = "Sign in to view balance"
            self._show_auth_required("Your session may have expired. Sign in again to continue.")
            return
        if notify:
            detail = "Your live balance could not be loaded. Check your connection and try again."
            self._set_feedback(detail, "error")
            self._show_popup("Balance Unavailable", detail)

    @staticmethod
    def _friendly_transfer_error(detail: str) -> str:
        message = str(detail or "").strip()
        normalized = message.lower()
        if "recipient user not found" in normalized:
            return "Recipient not found. Check the registered number."
        if "recipient_wallet_id" in normalized and "valid 10-digit registered number" in normalized:
            return "Enter a valid 10-digit registered number."
        if "recipient_wallet_id" in normalized and "required" in normalized:
            return "Recipient number is required."
        if "minimum p2p transfer amount is ghs 1.00" in normalized:
            return "Minimum transfer is GHS 1.00."
        if "cannot transfer funds to yourself" in normalized:
            return "You cannot send money to your own number."
        if "insufficient balance" in normalized:
            return "Insufficient balance for this amount and fee."
        return "Transfer could not be completed. Check the details and try again."

    def send_funds(self):
        if self.transfer_busy:
            return
        if not self.wallet_is_live:
            self._show_popup("Balance unavailable", "Refresh your live balance before sending. No funds have been sent.")
            return
        recipient = normalize_ghana_number(self.ids.recipient_input.text.strip())
        amount = self._parse_amount(self.ids.amount_input.text)

        if not recipient or len(recipient) != 10:
            self._show_popup("Check recipient", "Enter a valid registered Ghana MoMo number.")
            return
        if amount < MIN_P2P_TRANSFER_GHS:
            self._show_popup("Check amount", "Minimum transfer is GHS 1.00.")
            return

        fingerprint = (recipient, round(amount, 2))
        if fingerprint != self._transfer_idempotency_fingerprint:
            self._transfer_idempotency_key = uuid.uuid4().hex
            self._transfer_idempotency_fingerprint = fingerprint

        self.transfer_busy = True
        self.transfer_button_text = "Checking fees..."
        self._set_feedback("Checking today's fee allowance...", "info")
        self._transfer_generation += 1
        generation = self._transfer_generation

        if self._fee_loaded_at and time.monotonic() - self._fee_loaded_at <= 15:
            self._show_transfer_confirmation(recipient, amount, self._p2p_free_remaining, generation)
            return
        if self._fee_loading:
            self._pending_transfer = (recipient, amount, generation)
            return

        threading.Thread(
            target=self._prepare_transfer_worker,
            args=(recipient, amount, generation),
            daemon=True,
        ).start()

    def _prepare_transfer_worker(self, recipient: str, amount: float, generation: int) -> None:
        try:
            ok, payload = self._request("GET", "/wallet/p2p/fee-status")
        except Exception:
            ok, payload = False, {"detail": "Fee details are unavailable. Check your connection."}
        Clock.schedule_once(
            lambda _dt: self._apply_transfer_fee_check(ok, payload, recipient, amount, generation)
        )

    def _apply_transfer_fee_check(self, ok: bool, payload: object, recipient: str, amount: float, generation: int):
        if generation != self._transfer_generation:
            return
        if not self._is_screen_active():
            self._release_transfer()
            return
        if not ok or not isinstance(payload, dict):
            self._release_transfer()
            message = "Fee details could not be checked. Please try again when connected."
            if isinstance(payload, dict) and payload.get("_auth_required"):
                self._show_auth_required("Your session may have expired. Sign in again to continue.")
                return
            self._set_feedback(message, "warning")
            self._show_popup("Fee Details Unavailable", message)
            return

        free_limit = self._number(payload.get("p2p_daily_free_limit"), P2P_DAILY_FREE_LIMIT_GHS)
        if free_limit <= 0:
            free_limit = P2P_DAILY_FREE_LIMIT_GHS
        total_sent = self._number(payload.get("p2p_total_sent_today"), 0.0)
        free_remaining = self._number(payload.get("p2p_free_remaining"), max(0.0, free_limit - total_sent))
        self._p2p_free_limit = free_limit
        self._p2p_total_sent_today = total_sent
        self._p2p_free_remaining = min(free_limit, free_remaining)
        self._fee_loaded_at = time.monotonic()
        self.fee_status_text = f"Free today: GHS {self._p2p_free_remaining:,.2f}"
        self._show_transfer_confirmation(recipient, amount, self._p2p_free_remaining, generation)

    def _show_transfer_confirmation(self, recipient: str, amount: float, free_remaining: float, generation: int) -> None:
        feeable_amount = max(0.0, round(amount - free_remaining, 2))
        estimated_fee = round(feeable_amount * P2P_TRANSFER_FEE_RATE, 2)
        estimated_total = round(amount + estimated_fee, 2)
        message = (
            f"To: {recipient}\n"
            f"Amount: GHS {amount:,.2f}\n"
            f"Fee: GHS {estimated_fee:,.2f}\n"
            f"Total debit: GHS {estimated_total:,.2f}"
        )
        self.transfer_button_text = "Review and send"
        self._set_feedback("Review the amount, fee, and total.", "info")
        show_confirm_dialog(
            self,
            title="Confirm send",
            message=message,
            on_confirm=lambda: self._start_transfer(recipient, amount, estimated_fee, estimated_total, generation),
            on_cancel=self._release_transfer,
            confirm_label="Send",
            cancel_label="Cancel",
        )

    def _start_transfer(self, recipient: str, amount: float, estimated_fee: float, estimated_total: float, generation: int) -> None:
        if generation != self._transfer_generation or self._transfer_submitting:
            return
        self._transfer_submitting = True
        self.transfer_button_text = "Sending..."
        self._set_feedback("Sending securely?", "info")
        threading.Thread(
            target=self._transfer_worker,
            args=(recipient, amount, estimated_fee, estimated_total, generation),
            daemon=True,
        ).start()

    def _transfer_worker(self, recipient: str, amount: float, estimated_fee: float, estimated_total: float, generation: int) -> None:
        try:
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
                extra_headers={"Idempotency-Key": self._transfer_idempotency_key},
            )
        except Exception:
            ok, payload = False, {"detail": "Transfer could not be completed. Check your connection."}
        Clock.schedule_once(
            lambda _dt: self._apply_transfer_result(ok, payload, recipient, amount, estimated_fee, estimated_total, generation)
        )

    def _apply_transfer_result(self, ok: bool, payload: object, recipient: str, amount: float, estimated_fee: float, estimated_total: float, generation: int) -> None:
        if generation != self._transfer_generation:
            return
        self._transfer_submitting = False
        self._release_transfer()
        if not self._is_screen_active():
            if ok and isinstance(payload, dict):
                self.ids.recipient_input.text = ""
                self.ids.amount_input.text = ""
                self.update_transfer_preview("")
                self._transfer_idempotency_key = ""
                self._transfer_idempotency_fingerprint = None
                self.load_wallet()
                self.load_fee_status()
            return
        if ok and isinstance(payload, dict):
            charged_fee = self._number(payload.get("transfer_fee"), estimated_fee)
            total_debited = self._number(payload.get("total_debited"), estimated_total)
            reference = str(payload.get("transfer_reference") or "").strip()
            message = (
                f"Sent to {recipient}.\n"
                f"Amount: GHS {amount:,.2f}\n"
                f"Fee: GHS {charged_fee:,.2f}\n"
                f"Total debited: GHS {total_debited:,.2f}"
            )
            if reference:
                message = f"{message}\nRef: {reference}"
            self._set_feedback("", "success")
            self._show_popup("Transfer successful", message)
            self.ids.recipient_input.text = ""
            self.ids.amount_input.text = ""
            self.update_transfer_preview("")
            self._transfer_idempotency_key = ""
            self._transfer_idempotency_fingerprint = None
            self.load_wallet()
            self.load_fee_status()
            return

        detail = self._extract_detail(payload)
        if isinstance(payload, dict) and payload.get("_auth_required"):
            self._show_auth_required(detail or "Please sign in to continue.")
            return
        friendly = self._friendly_transfer_error(detail)
        self._set_feedback("", "error")
        self._show_popup("Transfer failed", friendly)

    def _is_screen_active(self) -> bool:
        manager = self.manager
        current = getattr(manager, "current_screen", None) if manager is not None else None
        return manager is None or current is None or current is self

    def _release_transfer(self, *_args) -> None:
        self.transfer_busy = False
        self.transfer_button_text = "Review and send"
        self._transfer_submitting = False

    def go_to_history(self):
        app = MDApp.get_running_app()
        if app is not None and hasattr(app, "go_to_screen"):
            if app.go_to_screen("transactions", fallback="p2p_transfer", transition_style="fade"):
                return
        if self.manager and self.manager.has_screen("transactions"):
            navigate(self.manager, "transactions", fallback="p2p_transfer", transition_style="fade")


Builder.load_string(KV)
