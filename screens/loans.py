from datetime import datetime, timezone, timedelta
from threading import Thread

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.lang import Builder
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField

from core.screen_actions import ActionScreen
from core.popup_manager import show_confirm_dialog, show_custom_dialog
from utils.formatter import safe_float

KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp
#:set BG (0.03, 0.04, 0.06, 1)
#:set SURFACE (0.08, 0.10, 0.14, 0.95)
#:set SURFACE_SOFT (0.12, 0.14, 0.18, 0.95)
#:set GOLD (0.94, 0.79, 0.46, 1)
#:set GOLD_SOFT (0.93, 0.77, 0.39, 1)
#:set GREEN_CARD (0.24, 0.43, 0.34, 0.96)
#:set RED_CARD (0.50, 0.20, 0.18, 0.96)
#:set TEXT_MAIN (0.95, 0.95, 0.95, 1)
#:set TEXT_SUB (0.74, 0.76, 0.80, 1)
<LoanScreen>:
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
                    height: dp(50 * root.layout_scale)

                    MDLabel:
                        text: "Loans"
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
                    md_bg_color: RED_CARD if root.loan_is_overdue else GREEN_CARD
                    elevation: 0
                    size_hint_y: None
                    height: dp(134 * root.layout_scale)
                    padding: [dp(14 * root.layout_scale)] * 4

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(4 * root.layout_scale)

                        MDLabel:
                            text: "Loan Balance"
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN

                        MDLabel:
                            text: root.loan_summary_amount
                            font_style: "Headline"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: GOLD
                            font_size: sp(28 * root.text_scale)

                        MDLabel:
                            text: root.loan_status_caption
                            theme_text_color: "Custom"
                            text_color: root.loan_status_color
                            font_size: sp(12 * root.text_scale)
                            shorten: True
                            shorten_from: "right"

                MDCard:
                    radius: [dp(20 * root.layout_scale)]
                    md_bg_color: SURFACE
                    elevation: 0
                    padding: [dp(14 * root.layout_scale)] * 4
                    adaptive_height: True

                    MDBoxLayout:
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: dp(6 * root.layout_scale)

                        MDLabel:
                            text: "Summary & Due"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: GOLD

                        MDLabel:
                            text: root.loan_summary
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(12 * root.text_scale)
                            adaptive_height: True

                        MDLabel:
                            text: root.loan_due_hint
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                        MDRaisedButton:
                            text: "Repay Loan" if root.manual_repayment_enabled else "Auto Repayment Active"
                            disabled: not root.manual_repayment_enabled
                            opacity: 1 if root.active_loan_id else 0
                            size_hint_y: None
                            height: dp(44 * root.layout_scale) if root.active_loan_id else 0
                            md_bg_color: GOLD_SOFT if root.manual_repayment_enabled else SURFACE_SOFT
                            text_color: BG if root.manual_repayment_enabled else TEXT_SUB
                            on_release: root.repay_loan()

                MDCard:
                    radius: [dp(20 * root.layout_scale)]
                    md_bg_color: SURFACE
                    elevation: 0
                    padding: [dp(14 * root.layout_scale)] * 4
                    adaptive_height: True

                    MDBoxLayout:
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: dp(6 * root.layout_scale)

                        MDLabel:
                            text: "Eligibility"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: GOLD

                        MDLabel:
                            text: root.eligibility_status_text
                            theme_text_color: "Custom"
                            text_color: root.eligibility_status_color
                            font_size: sp(12.5 * root.text_scale)
                            bold: True
                            adaptive_height: True

                        MDLabel:
                            text: root.eligible_amount_text
                            theme_text_color: "Custom"
                            text_color: GOLD
                            font_size: sp(14 * root.text_scale)
                            bold: True
                            adaptive_height: True

                        MDLabel:
                            text: root.eligibility_hint_text
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                MDCard:
                    radius: [dp(20 * root.layout_scale)]
                    md_bg_color: SURFACE
                    elevation: 0
                    padding: [dp(14 * root.layout_scale)] * 4
                    adaptive_height: True

                    MDBoxLayout:
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: dp(8 * root.layout_scale)

                        MDLabel:
                            text: "Request Loan"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: GOLD

                        MDLabel:
                            text: "Choose an amount and period. Your repayment total appears below."
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                        MDLabel:
                            text: "Loan amount"
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            font_size: sp(13 * root.text_scale)
                            adaptive_height: True

                        MDTextField:
                            id: apply_amount
                            hint_text: "Loan amount, e.g. 250"
                            mode: "rectangle"
                            input_filter: "float"
                            on_text: root.update_amount_preview(self.text)

                        MDLabel:
                            text: "Choose Repayment Period"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            adaptive_height: True

                        MDGridLayout:
                            cols: 2 if root.compact_mode else 4
                            adaptive_height: True
                            row_default_height: dp(42 * root.layout_scale)
                            row_force_default: True
                            spacing: dp(8 * root.layout_scale)

                            MDRaisedButton:
                                text: "1D"
                                disabled: not root.period_available(1)
                                opacity: 1 if root.period_available(1) else 0
                                height: dp(42 * root.layout_scale) if root.period_available(1) else 0
                                size_hint_y: None
                                md_bg_color: root.period_button_bg(1)
                                text_color: root.period_button_text_color(1)
                                on_release: root.set_duration(1)

                            MDRaisedButton:
                                text: "7D"
                                disabled: not root.period_available(7)
                                opacity: 1 if root.period_available(7) else 0
                                height: dp(42 * root.layout_scale) if root.period_available(7) else 0
                                size_hint_y: None
                                md_bg_color: root.period_button_bg(7)
                                text_color: root.period_button_text_color(7)
                                on_release: root.set_duration(7)

                            MDRaisedButton:
                                text: "14D"
                                disabled: not root.period_available(14)
                                opacity: 1 if root.period_available(14) else 0
                                height: dp(42 * root.layout_scale) if root.period_available(14) else 0
                                size_hint_y: None
                                md_bg_color: root.period_button_bg(14)
                                text_color: root.period_button_text_color(14)
                                on_release: root.set_duration(14)

                            MDRaisedButton:
                                text: "30D"
                                disabled: not root.period_available(30)
                                opacity: 1 if root.period_available(30) else 0
                                height: dp(42 * root.layout_scale) if root.period_available(30) else 0
                                size_hint_y: None
                                md_bg_color: root.period_button_bg(30)
                                text_color: root.period_button_text_color(30)
                                on_release: root.set_duration(30)

                            MDRaisedButton:
                                text: "60D"
                                disabled: not root.period_available(60)
                                opacity: 1 if root.period_available(60) else 0
                                height: dp(42 * root.layout_scale) if root.period_available(60) else 0
                                size_hint_y: None
                                md_bg_color: root.period_button_bg(60)
                                text_color: root.period_button_text_color(60)
                                on_release: root.set_duration(60)

                            MDRaisedButton:
                                text: "90D"
                                disabled: not root.period_available(90)
                                opacity: 1 if root.period_available(90) else 0
                                height: dp(42 * root.layout_scale) if root.period_available(90) else 0
                                size_hint_y: None
                                md_bg_color: root.period_button_bg(90)
                                text_color: root.period_button_text_color(90)
                                on_release: root.set_duration(90)

                        MDLabel:
                            text: "Selected period: {} days".format(int(root.selected_duration))
                            theme_text_color: "Custom"
                            text_color: GOLD
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                        MDLabel:
                            text: "Purpose"
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            font_size: sp(13 * root.text_scale)
                            adaptive_height: True

                        MDTextField:
                            id: apply_purpose
                            hint_text: "Purpose, e.g. stock or school fees"
                            mode: "rectangle"

                        MDLabel:
                            text: "Purpose is optional."
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                        MDLabel:
                            text: root.amount_preview_text
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                        MDRaisedButton:
                            id: apply_loan_button
                            text: "Request Loan"
                            disabled: root.loan_submit_busy
                            size_hint_y: None
                            height: dp(48 * root.layout_scale)
                            md_bg_color: GOLD_SOFT
                            text_color: BG
                            on_release: root.apply_loan()

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
            nav_variant: "default"
            active_target: ""
            layout_scale: root.layout_scale
            text_scale: root.text_scale
            icon_scale: root.icon_scale
            bar_color: app.ui_surface
            active_color: app.gold
            inactive_color: app.ui_text_secondary
"""


class LoanScreen(ActionScreen):
    page_subtitle = StringProperty("Request and manage wallet loans.")
    loan_status_title = StringProperty("No Loan")
    loan_status_color = ListProperty([0.74, 0.76, 0.80, 1])
    loan_status_caption = StringProperty("No active loan right now.")
    loan_summary_amount = StringProperty("GHS 0.00")
    loan_summary = StringProperty(
        "Choose an amount and period to preview your total repayment."
    )
    loan_due_hint = StringProperty("Users can choose 1, 7, 14, or 30 days. Active agents can also choose 60 or 90 days.")
    amount_preview_text = StringProperty(
        "Enter a loan amount to preview total repayment, service fee, and the overdue fee."
    )
    feedback_hint = StringProperty("")
    manual_repayment_text = StringProperty(
        "Load your active loan to see if manual repayment is available."
    )
    allowed_periods = ListProperty([1, 7, 14, 30])
    selected_duration = NumericProperty(7)
    active_loan_id = NumericProperty(0)
    outstanding_balance = NumericProperty(0.0)
    loan_is_overdue = BooleanProperty(False)
    is_agent_eligible = BooleanProperty(False)
    manual_repayment_enabled = BooleanProperty(False)
    transaction_volume_total = NumericProperty(0.0)
    eligible_amount_total = NumericProperty(0.0)
    eligibility_status_text = StringProperty("Checking eligibility...")
    eligibility_hint_text = StringProperty(
        "Your eligible limit is based on 25% of your last 30 days total transactions."
    )
    eligibility_status_color = ListProperty([0.74, 0.76, 0.80, 1])
    transaction_volume_text = StringProperty("GHS 0.00")
    eligible_amount_text = StringProperty("GHS 0.00")
    loan_refresh_busy = BooleanProperty(False)
    loan_submit_busy = BooleanProperty(False)
    repayment_busy = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._loan_refresh_generation = 0
        self._loan_refresh_pending = 0
        self._repay_dialog = None
        self._repay_amount_field = None

    @staticmethod
    def _parse_float(raw: str) -> float:
        try:
            return float(str(raw or "").strip())
        except Exception:
            return 0.0

    @staticmethod
    def _parse_int(raw: str) -> int:
        try:
            return int(str(raw or "").strip())
        except Exception:
            return 0

    def on_pre_enter(self):
        self.refresh_loans(silent=True)
        Clock.schedule_once(lambda *_args: self.update_amount_preview(self.ids.apply_amount.text if "apply_amount" in self.ids else ""), 0.1)

    def _set_manual_repayment_state(self, enabled: bool, message: str = "") -> None:
        self.manual_repayment_enabled = bool(enabled)
        fallback = (
            "Manual repayment is available while the loan stays on schedule."
            if enabled
            else "Manual repayment is not available right now."
        )
        self.manual_repayment_text = str(message or "").strip() or fallback

    def _ensure_selected_duration(self) -> None:
        options = [int(item) for item in self.allowed_periods] or [1]
        if int(self.selected_duration or 0) in options:
            return
        self.selected_duration = 7 if 7 in options else options[0]

    def period_available(self, days: int) -> bool:
        return int(days) in [int(item) for item in self.allowed_periods]

    def period_button_bg(self, days: int):
        if int(days) == int(self.selected_duration):
            return [0.93, 0.77, 0.39, 1]
        return [0.12, 0.14, 0.18, 0.95]

    def period_button_text_color(self, days: int):
        if int(days) == int(self.selected_duration):
            return [0.03, 0.04, 0.06, 1]
        return [0.95, 0.95, 0.95, 1]

    def set_duration(self, days: int) -> None:
        if not self.period_available(days):
            self._set_feedback("That repayment period is not available for your account.", "warning")
            return
        self.selected_duration = int(days)
        self.update_amount_preview(self.ids.apply_amount.text if "apply_amount" in self.ids else "")

    # Kept for callers from older screen code.
    select_duration = set_duration

    def refresh_loans(self, silent: bool = False) -> bool:
        """Refresh loan policy, eligibility, and active balance without blocking the UI."""
        if self.loan_refresh_busy:
            return False
        self.loan_refresh_busy = True
        self._loan_refresh_generation += 1
        generation = self._loan_refresh_generation
        self._loan_refresh_pending = 3
        if not silent:
            self._set_feedback("Refreshing loan details…", "info")

        requests = (
            ("policy", "GET", "/loans/my-policy", None),
            ("eligibility", "GET", "/wallet/transactions/me", {"limit": 1000}),
            ("active", "GET", "/loans/my-active-loan", None),
        )
        for kind, method, path, params in requests:
            try:
                Thread(
                    target=self._load_loan_refresh_piece,
                    args=(generation, kind, method, path, params),
                    daemon=True,
                ).start()
            except Exception as exc:
                result = (False, {"detail": str(exc) or "Unable to refresh loan details."})
                Clock.schedule_once(
                    lambda _dt, piece=kind, response=result: self._apply_loan_refresh_piece(
                        generation, piece, response
                    ),
                    0,
                )
        return True

    def _load_loan_refresh_piece(self, generation, kind, method, path, params) -> None:
        try:
            result = self._request(method, path, params=params)
        except Exception as exc:
            result = (False, {"detail": str(exc) or "Unable to refresh loan details."})
        Clock.schedule_once(
            lambda _dt: self._apply_loan_refresh_piece(generation, kind, result),
            0,
        )

    def _apply_loan_refresh_piece(self, generation, kind, result) -> None:
        if generation != self._loan_refresh_generation:
            return
        try:
            if kind == "policy":
                self.load_policy(result)
            elif kind == "eligibility":
                self.load_eligibility(result)
            else:
                self.view_active_loan(show_popup=False, response=result)
        except Exception:
            self._set_feedback("Some loan details could not be refreshed. Pull down to try again.", "warning")
        finally:
            self._loan_refresh_pending = max(0, self._loan_refresh_pending - 1)
            if self._loan_refresh_pending == 0:
                self.loan_refresh_busy = False
                self._finish_pull_refresh()

    @staticmethod
    def _format_due_date(raw_value: object) -> str:
        raw_text = str(raw_value or "").strip()
        if not raw_text:
            return "No due date yet"
        try:
            due_at = datetime.fromisoformat(raw_text.replace("Z", "+00:00"))
        except Exception:
            return raw_text
        return due_at.strftime("%d %b %Y, %I:%M %p")

    def load_policy(self, response=None) -> None:
        if response is None:
            response = self._request("GET", "/loans/my-policy")
        ok, payload = response
        if ok and isinstance(payload, dict):
            raw_periods = payload.get("allowed_periods")
            if not isinstance(raw_periods, list):
                raw_periods = [1, 7, 14, 30]
            self.allowed_periods = sorted({days for item in raw_periods if (days := self._parse_int(item)) > 0})
            if not self.allowed_periods:
                self.allowed_periods = [1, 7, 14, 30]
            self.is_agent_eligible = bool(payload.get("is_agent_eligible", False))
            self._ensure_selected_duration()
            self.update_amount_preview(self.ids.apply_amount.text if "apply_amount" in self.ids else "")
            return

        self.allowed_periods = [1, 7, 14, 30]
        self.is_agent_eligible = False
        self._ensure_selected_duration()

    def load_eligibility(self, response=None) -> None:
        self.eligibility_status_text = "Calculating eligibility..."
        self.eligibility_status_color = [0.74, 0.76, 0.80, 1]
        if response is None:
            response = self._request("GET", "/wallet/transactions/me", params={"limit": 1000})
        ok, payload = response
        if ok and isinstance(payload, list):
            total_volume = 0.0
            unknown_count = 0
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            for item in payload:
                if not isinstance(item, dict):
                    continue
                raw_ts = item.get("timestamp") or item.get("created_at") or item.get("date") or ""
                if raw_ts:
                    try:
                        parsed = datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00"))
                        if parsed.tzinfo is None:
                            parsed = parsed.replace(tzinfo=timezone.utc)
                    except Exception:
                        parsed = None
                else:
                    parsed = None

                if parsed is None:
                    unknown_count += 1
                    continue
                if parsed < cutoff:
                    continue
                amount = safe_float(item.get("amount"))
                total_volume += abs(amount)

            self.transaction_volume_total = round(total_volume, 2)
            self.transaction_volume_text = f"GHS {self.transaction_volume_total:,.2f}"

            suffix = f" ({unknown_count} undated transaction(s) excluded)" if unknown_count else ""
            if self.transaction_volume_total >= 200.0:
                self.eligible_amount_total = round(self.transaction_volume_total * 0.25, 2)
                self.eligible_amount_text = f"GHS {self.eligible_amount_total:,.2f}"
                self.eligibility_status_text = "Eligible for a wallet loan"
                self.eligibility_status_color = [0.60, 0.88, 0.72, 1]
                self.eligibility_hint_text = (
                    "You can request up to 25% of your last 30 days total transactions." + suffix
                )
            else:
                remaining = max(0.0, round(200.0 - self.transaction_volume_total, 2))
                self.eligible_amount_total = 0.0
                self.eligible_amount_text = "GHS 0.00"
                self.eligibility_status_text = "Not eligible yet"
                self.eligibility_status_color = [0.98, 0.48, 0.41, 1]
                self.eligibility_hint_text = (
                    f"Complete at least GHS 200 in the last 30 days total transactions. Remaining: GHS {remaining:,.2f}.{suffix}"
                )
            return

        self.transaction_volume_total = 0.0
        self.eligible_amount_total = 0.0
        self.transaction_volume_text = "GHS 0.00"
        self.eligible_amount_text = "GHS 0.00"
        self.eligibility_status_text = "Eligibility unavailable"
        self.eligibility_status_color = [0.98, 0.48, 0.41, 1]
        self.eligibility_hint_text = "We could not load transactions. Please refresh later."

    def update_amount_preview(self, raw_amount: str) -> None:
        amount = self._parse_float(raw_amount)
        duration = int(self.selected_duration or 0)
        if amount <= 0 or duration <= 0:
            self.amount_preview_text = (
                "Enter a loan amount to preview your scheduled repayment, service fee, and overdue fee."
            )
            return

        service_fee = round(amount * 0.15, 2)
        scheduled_total = round(amount + service_fee, 2)
        overdue_fee = round(amount * 0.20, 2)
        day_label = "day" if duration == 1 else "days"
        self.amount_preview_text = (
            f"Repay GHS {scheduled_total:,.2f} within {duration} {day_label} "
            f"(includes GHS {service_fee:,.2f} service fee). Late fee may be GHS {overdue_fee:,.2f}."
        )

    def apply_loan(self):
        if self.loan_submit_busy:
            return
        amount = self._parse_float(self.ids.apply_amount.text)
        duration = int(self.selected_duration or 0)
        purpose = str(self.ids.apply_purpose.text or "").strip()

        if self.transaction_volume_total < 200.0:
            self._set_feedback("You are not eligible for a loan yet.", "error")
            self._show_popup("Not Eligible", "At least GHS 200 in recent transactions is required.")
            return
        if self.eligible_amount_total > 0 and amount > self.eligible_amount_total:
            self._set_feedback("Requested amount exceeds your eligible limit.", "error")
            self._show_popup("Amount Too High", f"Your current maximum is {self.eligible_amount_text}.")
            return
        if amount <= 0:
            self._set_feedback("Enter a valid loan amount in Ghana cedis.", "error")
            self._show_popup("Invalid Amount", "Enter an amount greater than zero.")
            return
        if duration <= 0 or not self.period_available(duration):
            self._set_feedback("Select an available repayment period.", "error")
            self._show_popup("Invalid Period", "Choose one of the periods enabled for your account.")
            return

        self.loan_submit_busy = True
        self._set_feedback("Submitting your loan request...", "info")
        self.feedback_hint = "You can keep this screen open while we process it."
        try:
            Thread(
                target=self._submit_loan_worker,
                args=(amount, duration, purpose),
                daemon=True,
            ).start()
        except Exception:
            self.loan_submit_busy = False
            self._set_feedback("Unable to start the loan request. Please try again.", "error")

    def _submit_loan_worker(self, amount: float, duration: int, purpose: str) -> None:
        try:
            result = self._request(
                "POST",
                "/loans/apply",
                payload={
                    "amount": amount,
                    "repayment_duration": duration,
                    "purpose": purpose or None,
                },
            )
        except Exception as exc:
            result = (False, {"detail": str(exc) or "Unable to process the loan request."})
        Clock.schedule_once(lambda _dt: self._finish_loan_submission(result), 0)

    def _finish_loan_submission(self, result) -> None:
        self.loan_submit_busy = False
        ok, payload = result
        if ok and isinstance(payload, dict):
            app_id = payload.get("id")
            message = "Loan approved and credited to your wallet."
            if app_id:
                message = f"{message} Reference #{app_id}."
            self.ids.apply_amount.text = ""
            self.ids.apply_purpose.text = ""
            self.update_amount_preview("")
            self._set_feedback(message, "success")
            self.feedback_hint = "Your loan balance is refreshing."
            self.refresh_loans(silent=True)
            self._show_popup("Loan Ready", message)
            return
        detail = self._extract_detail(payload) or "Unable to process your loan request."
        self._set_feedback(detail, "error")
        self.feedback_hint = "Review your amount and period, then try again."
        self._show_popup("Loan Request Failed", detail)

    def view_active_loan(self, show_popup: bool = True, response=None):
        if response is None:
            self._set_feedback("Loading your current loan…", "info")
            response = self._request("GET", "/loans/my-active-loan")
        ok, payload = response
        if ok:
            if not payload:
                self.active_loan_id = 0
                self.outstanding_balance = 0.0
                self.loan_is_overdue = False
                self.loan_status_title = "No Loan"
                self.loan_status_color = [0.74, 0.76, 0.80, 1]
                self.loan_status_caption = "No active loan. Request one below."
                self.loan_summary_amount = "GHS 0.00"
                self.loan_summary = "You do not have any open loan right now. Request one below."
                self.loan_due_hint = "Incoming wallet credits only sweep while a loan is open."
                self._set_manual_repayment_state(
                    False,
                    "Manual repayment will appear here when you have an active on-schedule loan.",
                )
                self._set_feedback("No open loan found.", "warning")
                self.feedback_hint = "If you just borrowed, wait briefly and tap Refresh Loan again."
                if show_popup:
                    self._show_popup("No Open Loan", "You currently do not have any open loan.")
                return

            if isinstance(payload, dict):
                loan_id = self._parse_int(payload.get("id"))
                amount = safe_float(payload.get("amount"))
                remaining = safe_float(payload.get("remaining_balance", payload.get("outstanding_balance", 0.0)))
                base_fee_amount = safe_float(payload.get("base_fee_amount"))
                late_fee_amount = safe_float(payload.get("late_fee_amount"))
                status_text = str(payload.get("status", "active") or "active").strip().lower()
                self.loan_is_overdue = bool(payload.get("is_overdue", False)) or status_text == "overdue"
                manual_repayment_allowed = bool(payload.get("manual_repayment_allowed", not self.loan_is_overdue))
                manual_repayment_message = str(payload.get("manual_repayment_message", "") or "").strip()
                due_text = self._format_due_date(payload.get("repayment_due_date"))

                self.active_loan_id = loan_id
                self.outstanding_balance = max(0.0, remaining)
                if self.loan_is_overdue:
                    self.loan_status_title = "Overdue"
                    self.loan_status_color = [0.98, 0.48, 0.41, 1]
                    self.loan_status_caption = "Overdue balance"
                else:
                    self.loan_status_title = "Active"
                    self.loan_status_color = [0.60, 0.88, 0.72, 1]
                    self.loan_status_caption = "Outstanding balance"
                self.loan_summary_amount = f"GHS {remaining:,.2f}"
                self.loan_summary = (
                    f"Loan #{loan_id} | Principal: GHS {amount:,.2f} | Remaining: GHS {remaining:,.2f} | "
                    f"Fee: GHS {base_fee_amount:,.2f}."
                )
                if late_fee_amount > 0:
                    self.loan_summary += f" Overdue fee: GHS {late_fee_amount:,.2f}."
                if self.loan_is_overdue and late_fee_amount <= 0:
                    self.loan_due_hint = f"Overdue since {due_text}. Clear within 24 hours to avoid the extra fee."
                elif self.loan_is_overdue:
                    self.loan_due_hint = f"Overdue. Extra fee already added. Original due date: {due_text}."
                else:
                    self.loan_due_hint = f"Due on {due_text}. Incoming wallet credits can sweep this balance automatically."
                if manual_repayment_allowed:
                    self._set_manual_repayment_state(
                        True,
                        manual_repayment_message or "Choose an amount to repay from your wallet.",
                    )
                else:
                    self._set_manual_repayment_state(
                        False,
                        manual_repayment_message
                        or "Manual repayment is unavailable. Incoming wallet funds may be used for recovery.",
                    )
                self._set_feedback("Loan details updated.", "success")
                if self.manual_repayment_enabled:
                    self.feedback_hint = "You can repay manually below or wait for future incoming wallet credits to sweep the balance."
                else:
                    self.feedback_hint = "Manual repayment is locked for overdue loans. Add funds to your wallet to continue automatic recovery."
                return

        detail = self._extract_detail(payload) or "Unable to load your loan details."
        self.active_loan_id = 0
        self.outstanding_balance = 0.0
        self.loan_is_overdue = False
        self.loan_status_title = "Sync Error"
        self.loan_status_color = [0.98, 0.48, 0.41, 1]
        self.loan_status_caption = "Unable to load loan status."
        self.loan_summary_amount = "GHS 0.00"
        self.loan_summary = "We could not refresh your loan details right now."
        self.loan_due_hint = "Please try again when your connection is stable."
        self._set_manual_repayment_state(
            False,
            "Manual repayment is temporarily unavailable until your latest loan details finish loading.",
        )
        self._set_feedback(detail, "error")
        self.feedback_hint = "Refresh the screen and try again."
        if show_popup:
            self._show_popup("Loan Sync Error", detail)

    def repay_loan(self):
        if not self.active_loan_id:
            self._set_feedback("No active loan is loaded.", "warning")
            self._show_popup("No Open Loan", "Refresh the Loans screen to check your current balance.")
            return
        if not self.manual_repayment_enabled:
            self._set_feedback("Manual repayment is unavailable for this loan.", "warning")
            self._show_popup("Repayment Unavailable", self.manual_repayment_text)
            return
        if self.repayment_busy or self._repay_dialog is not None:
            return

        balance = max(0.0, safe_float(self.outstanding_balance))
        layout = MDBoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=(dp(8), dp(8), dp(8), dp(8)),
            size_hint_y=None,
            height=dp(152),
        )
        layout.add_widget(MDLabel(
            text=f"Outstanding balance: GHS {balance:,.2f}",
            adaptive_height=True,
            theme_text_color="Primary",
        ))
        amount_field = MDTextField(
            hint_text="Amount to repay",
            text=f"{balance:.2f}" if balance > 0 else "",
            input_filter="float",
            mode="rectangle",
            size_hint_y=None,
            height=dp(52),
        )
        self._repay_amount_field = amount_field
        layout.add_widget(amount_field)
        layout.add_widget(MDLabel(
            text="Payment uses your available wallet balance and may be partial.",
            adaptive_height=True,
            theme_text_color="Secondary",
        ))

        def review_repayment(*_args):
            amount = self._parse_float(amount_field.text)
            if amount <= 0 or amount > balance:
                self._set_feedback("Enter an amount up to your outstanding balance.", "error")
                self._show_popup("Check Repayment Amount", f"Enter an amount from GHS 0.01 to GHS {balance:,.2f}.")
                return
            self._clear_repay_dialog()
            show_confirm_dialog(
                self,
                title="Confirm Repayment",
                message=f"Apply up to GHS {amount:,.2f} toward this loan from your available wallet balance?",
                confirm_label="Repay Now",
                cancel_label="Cancel",
                on_confirm=lambda: self._submit_repayment(amount),
            )

        layout.add_widget(MDRaisedButton(
            text="Continue",
            size_hint_y=None,
            height=dp(44),
            on_release=review_repayment,
        ))
        self._repay_dialog = show_custom_dialog(
            self,
            title="Repay Loan",
            content_cls=layout,
            close_label="Cancel",
            on_close=self._clear_repay_dialog,
        )

    def _clear_repay_dialog(self) -> None:
        self._repay_dialog = None
        self._repay_amount_field = None

    def _submit_repayment(self, amount: float) -> None:
        if self.repayment_busy or not self.active_loan_id:
            return
        self.repayment_busy = True
        self._set_feedback("Processing your repayment...", "info")
        self.feedback_hint = "Your wallet and loan balance will refresh when processing finishes."
        try:
            Thread(
                target=self._repayment_worker,
                args=(int(self.active_loan_id), float(amount)),
                daemon=True,
            ).start()
        except Exception:
            self.repayment_busy = False
            self._set_feedback("Unable to start repayment. Please try again.", "error")

    def _repayment_worker(self, loan_id: int, amount: float) -> None:
        try:
            result = self._request(
                "POST",
                f"/loans/{loan_id}/repay",
                params={"repayment_amount": amount},
            )
        except Exception as exc:
            result = (False, {"detail": str(exc) or "Unable to process your repayment."})
        Clock.schedule_once(lambda _dt: self._finish_repayment(result), 0)

    def _finish_repayment(self, result) -> None:
        self.repayment_busy = False
        ok, payload = result
        if ok and isinstance(payload, dict):
            remaining = safe_float(payload.get("remaining_balance", payload.get("outstanding_balance", 0.0)))
            message = (
                "Repayment successful. Your loan is cleared."
                if remaining <= 0
                else f"Repayment successful. Remaining balance: GHS {remaining:,.2f}."
            )
            self._set_feedback(message, "success")
            self.feedback_hint = "Your latest loan balance is loading."
            self.refresh_loans(silent=True)
            self._show_popup("Repayment Successful", message)
            return
        detail = self._extract_detail(payload) or "Unable to process your repayment."
        self._set_feedback(detail, "error")
        self.feedback_hint = "Check your wallet balance and try again."
        self._show_popup("Repayment Failed", detail)


Builder.load_string(KV)
