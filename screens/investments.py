import json
from datetime import datetime

from kivy.lang import Builder
from kivy.properties import StringProperty

from core.screen_actions import ActionScreen

INVESTMENT_MIN_AMOUNT_GHS = 10.0
STANDARD_ANNUAL_RATE_PCT = 12.0
STANDARD_PROFIT_FEE_RATE = 0.10
ALLOWED_INVESTMENT_PERIODS = (7, 14, 30, 60, 90, 180, 365)
DEFAULT_INVESTMENT_PERIOD_DAYS = 30

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
<InvestmentScreen>:
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
                    height: dp(50 * root.layout_scale)

                    MDLabel:
                        text: "Investments"
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
                    height: dp(140 * root.layout_scale)
                    padding: [dp(14 * root.layout_scale)] * 4

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(4 * root.layout_scale)

                        MDLabel:
                            text: "Main Balance"
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN

                        MDLabel:
                            text: root.main_balance_display
                            font_style: "Headline"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: GOLD
                            font_size: sp(28 * root.text_scale)

                        MDLabel:
                            text: root.lock_note_text
                            theme_text_color: "Custom"
                            text_color: 0.80, 0.92, 0.80, 1
                            font_size: sp(12 * root.text_scale)

                MDCard:
                    radius: [dp(20 * root.layout_scale)]
                    md_bg_color: SURFACE
                    elevation: 0
                    padding: [dp(14 * root.layout_scale)] * 4
                    adaptive_height: True

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(10 * root.layout_scale)
                        adaptive_height: True

                        MDLabel:
                            text: "Invest Main Balance"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: GOLD

                        MDLabel:
                            text: "Minimum GHS 10.00. Standard annual rate is 12% with a 10% fee on gross profit."
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(12 * root.text_scale)
                            adaptive_height: True

                        MDTextField:
                            id: invest_amount
                            hint_text: "Amount to invest"
                            mode: "outlined"
                            input_filter: "float"
                            on_text: root.update_projection(self.text)

                        MDLabel:
                            text: "Choose Investment Period"
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            bold: True
                            font_size: sp(12 * root.text_scale)
                            adaptive_height: True

                        MDGridLayout:
                            cols: 2 if root.compact_mode else 4
                            spacing: dp(6 * root.layout_scale)
                            size_hint_y: None
                            height: self.minimum_height

                            MDRaisedButton:
                                text: "7D"
                                md_bg_color: GOLD_SOFT if root.selected_duration_text == "7" else SURFACE_SOFT
                                text_color: BG if root.selected_duration_text == "7" else TEXT_MAIN
                                size_hint_y: None
                                height: dp(42 * root.layout_scale)
                                on_release: root.set_duration(7)
                            MDRaisedButton:
                                text: "14D"
                                md_bg_color: GOLD_SOFT if root.selected_duration_text == "14" else SURFACE_SOFT
                                text_color: BG if root.selected_duration_text == "14" else TEXT_MAIN
                                size_hint_y: None
                                height: dp(42 * root.layout_scale)
                                on_release: root.set_duration(14)
                            MDRaisedButton:
                                text: "30D"
                                md_bg_color: GOLD_SOFT if root.selected_duration_text == "30" else SURFACE_SOFT
                                text_color: BG if root.selected_duration_text == "30" else TEXT_MAIN
                                size_hint_y: None
                                height: dp(42 * root.layout_scale)
                                on_release: root.set_duration(30)
                            MDRaisedButton:
                                text: "60D"
                                md_bg_color: GOLD_SOFT if root.selected_duration_text == "60" else SURFACE_SOFT
                                text_color: BG if root.selected_duration_text == "60" else TEXT_MAIN
                                size_hint_y: None
                                height: dp(42 * root.layout_scale)
                                on_release: root.set_duration(60)
                            MDRaisedButton:
                                text: "90D"
                                md_bg_color: GOLD_SOFT if root.selected_duration_text == "90" else SURFACE_SOFT
                                text_color: BG if root.selected_duration_text == "90" else TEXT_MAIN
                                size_hint_y: None
                                height: dp(42 * root.layout_scale)
                                on_release: root.set_duration(90)
                            MDRaisedButton:
                                text: "180D"
                                md_bg_color: GOLD_SOFT if root.selected_duration_text == "180" else SURFACE_SOFT
                                text_color: BG if root.selected_duration_text == "180" else TEXT_MAIN
                                size_hint_y: None
                                height: dp(42 * root.layout_scale)
                                on_release: root.set_duration(180)
                            MDRaisedButton:
                                text: "365D"
                                md_bg_color: GOLD_SOFT if root.selected_duration_text == "365" else SURFACE_SOFT
                                text_color: BG if root.selected_duration_text == "365" else TEXT_MAIN
                                size_hint_y: None
                                height: dp(42 * root.layout_scale)
                                on_release: root.set_duration(365)

                        MDLabel:
                            text: "Selected period: " + root.selected_duration_text + " days"
                            theme_text_color: "Custom"
                            text_color: GOLD
                            font_size: sp(12 * root.text_scale)
                            adaptive_height: True

                        MDLabel:
                            text: root.projection_text
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(12 * root.text_scale)
                            adaptive_height: True

                        MDRaisedButton:
                            text: "Invest Now"
                            md_bg_color: GOLD_SOFT
                            text_color: BG
                            size_hint_y: None
                            height: dp(48 * root.layout_scale)
                            on_release: root.create_investment()

                MDCard:
                    radius: [dp(20 * root.layout_scale)]
                    md_bg_color: SURFACE
                    elevation: 0
                    padding: [dp(14 * root.layout_scale)] * 4
                    adaptive_height: True

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(8 * root.layout_scale)
                        adaptive_height: True

                        MDLabel:
                            text: "Unlock Matured Investment"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: GOLD

                        MDTextField:
                            id: payout_id
                            hint_text: "Investment ID"
                            mode: "outlined"
                            input_filter: "int"

                        MDGridLayout:
                            cols: 1 if root.compact_mode else 2
                            spacing: dp(8 * root.layout_scale)
                            adaptive_height: True
                            size_hint_y: None
                            height: self.minimum_height

                            MDRaisedButton:
                                text: "Load Active"
                                size_hint_y: None
                                height: dp(46 * root.layout_scale)
                                on_release: root.load_last_active_investment()

                            MDRaisedButton:
                                text: "Payout"
                                size_hint_y: None
                                height: dp(46 * root.layout_scale)
                                on_release: root.payout_investment()

                MDLabel:
                    text: root.investment_summary
                    theme_text_color: "Custom"
                    text_color: TEXT_SUB
                    adaptive_height: True

                MDLabel:
                    text: root.feedback_text
                    theme_text_color: "Custom"
                    text_color: root.feedback_color
                    adaptive_height: True

                Widget:
                    size_hint_y: None
                    height: dp(8 * root.layout_scale)

        BottomNavBar:
            nav_variant: "default"
            active_target: ""
            layout_scale: root.layout_scale
            text_scale: root.text_scale
            icon_scale: root.icon_scale
"""


class InvestmentScreen(ActionScreen):
    investment_summary = StringProperty("No active investment loaded.")
    main_balance_display = StringProperty("GHS 0.00")
    selected_duration_text = StringProperty(str(DEFAULT_INVESTMENT_PERIOD_DAYS))
    projection_text = StringProperty("Enter amount and pick a period to preview your standard profit.")
    lock_note_text = StringProperty(
        "Investments use your main balance and stay locked until the selected period ends."
    )

    def on_pre_enter(self):
        if self.selected_duration_text not in {str(item) for item in ALLOWED_INVESTMENT_PERIODS}:
            self.selected_duration_text = str(DEFAULT_INVESTMENT_PERIOD_DAYS)
        self.load_wallet_balance(notify=False)
        self.update_projection()

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

    @staticmethod
    def _parse_metadata(raw_meta: object) -> dict:
        if isinstance(raw_meta, dict):
            return raw_meta
        if isinstance(raw_meta, str) and raw_meta.strip():
            try:
                parsed = json.loads(raw_meta)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                return {}
        return {}

    @staticmethod
    def _format_date_short(iso_value: str) -> str:
        raw = str(iso_value or "").strip()
        if not raw:
            return "N/A"
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt.strftime("%d %b %Y")
        except Exception:
            return raw[:10]

    def _selected_duration_days(self) -> int:
        selected = self._parse_int(self.selected_duration_text)
        if selected not in ALLOWED_INVESTMENT_PERIODS:
            return DEFAULT_INVESTMENT_PERIOD_DAYS
        return selected

    def load_wallet_balance(self, notify: bool = True):
        ok, payload = self._request("GET", "/wallet/me")
        if ok and isinstance(payload, dict):
            balance = float(payload.get("balance", 0.0) or 0.0)
            self.main_balance_display = f"GHS {balance:,.2f}"
            if notify:
                self._set_feedback("Main balance updated.", "success")
            return

        detail = self._extract_detail(payload) or "Unable to load main balance."
        self._set_feedback(detail, "error")
        if notify:
            self._show_popup("Balance Sync Error", detail)

    def set_duration(self, days: int):
        selected = int(days or 0)
        if selected not in ALLOWED_INVESTMENT_PERIODS:
            allowed_text = ", ".join(str(item) for item in ALLOWED_INVESTMENT_PERIODS)
            self._set_feedback(f"Unsupported period. Choose: {allowed_text} days.", "error")
            return
        self.selected_duration_text = str(selected)
        self.update_projection()

    def update_projection(self, *_args):
        amount = self._parse_float(self.ids.invest_amount.text if "invest_amount" in self.ids else "")
        duration = self._selected_duration_days()

        if amount < INVESTMENT_MIN_AMOUNT_GHS:
            self.projection_text = (
                "Enter at least GHS 10.00 to preview projected gross profit, 10% profit fee, "
                "and net profit at maturity."
            )
            return

        gross_profit = round(amount * (STANDARD_ANNUAL_RATE_PCT / 100.0) * (duration / 365.0), 2)
        profit_fee = round(gross_profit * STANDARD_PROFIT_FEE_RATE, 2)
        net_profit = round(gross_profit - profit_fee, 2)
        self.projection_text = (
            f"{duration} days at {STANDARD_ANNUAL_RATE_PCT:.0f}% p.a.: "
            f"Gross GHS {gross_profit:,.2f} | "
            f"Fee (10%) GHS {profit_fee:,.2f} | "
            f"Net GHS {net_profit:,.2f}."
        )

    def create_investment(self):
        amount = self._parse_float(self.ids.invest_amount.text)
        duration = self._selected_duration_days()

        if amount < INVESTMENT_MIN_AMOUNT_GHS:
            self._set_feedback("Minimum investment is GHS 10.00.", "error")
            self._show_popup("Invalid Amount", "Please enter an amount from GHS 10.00 or more.")
            return
        if duration not in ALLOWED_INVESTMENT_PERIODS:
            allowed_text = ", ".join(str(item) for item in ALLOWED_INVESTMENT_PERIODS)
            self._set_feedback("Unsupported investment period selected.", "error")
            self._show_popup("Invalid Period", f"Choose one of these periods: {allowed_text} days.")
            return

        self._set_feedback("Creating investment from main balance...", "info")
        ok, payload = self._request(
            "POST",
            "/transactions/investment/create",
            payload={"amount": amount, "duration_days": duration},
        )
        if ok and isinstance(payload, dict):
            tx_id = int(payload.get("id", 0) or 0)
            metadata = self._parse_metadata(payload.get("metadata_json"))
            projected_fee = float(metadata.get("projected_profit_fee", 0.0) or 0.0)
            projected_net = float(metadata.get("projected_net_profit", 0.0) or 0.0)
            maturity_date = self._format_date_short(str(metadata.get("maturity_at") or ""))

            if tx_id > 0:
                self.ids.payout_id.text = str(tx_id)

            message = (
                f"Investment created from main balance.\n"
                f"Period: {duration} days\n"
                f"Projected fee (10%): GHS {projected_fee:,.2f}\n"
                f"Projected net profit: GHS {projected_net:,.2f}\n"
                f"Locked until: {maturity_date}"
            )
            self.investment_summary = (
                f"Investment #{tx_id if tx_id > 0 else '-'} | Principal: GHS {amount:,.2f} | "
                f"Period: {duration}D | Locked until {maturity_date}"
            )
            self._set_feedback("Investment created successfully.", "success")
            self._show_popup("Investment Created", message)
            self.ids.invest_amount.text = ""
            self.update_projection()
            self.load_wallet_balance(notify=False)
            return

        detail = self._extract_detail(payload) or "Unable to create investment."
        self._set_feedback(detail, "error")
        self._show_popup("Investment Failed", detail)

    def load_last_active_investment(self):
        self._set_feedback("Loading active investments...", "info")
        ok, payload = self._request("GET", "/wallet/transactions/me", params={"limit": 100})
        if not ok or not isinstance(payload, list):
            detail = self._extract_detail(payload) or "Unable to load investments."
            self._set_feedback(detail, "error")
            self._show_popup("Load Failed", detail)
            return

        active_item = None
        for tx in payload:
            if str(tx.get("type", "")).strip().lower() != "investment_create":
                continue
            metadata = self._parse_metadata(tx.get("metadata_json"))
            status_value = str(metadata.get("investment_status", "active")).strip().lower()
            if status_value == "active":
                active_item = tx
                break

        if not active_item:
            self.investment_summary = "No active investment found."
            self._set_feedback("No active investment found.", "warning")
            self._show_popup(
                "No Active Investment",
                "No active investment is available. Create one from your main balance to begin earning standard profit.",
            )
            return

        inv_id = int(active_item.get("id", 0) or 0)
        amount = float(active_item.get("amount", 0.0) or 0.0)
        metadata = self._parse_metadata(active_item.get("metadata_json"))
        duration = int(metadata.get("duration_days", DEFAULT_INVESTMENT_PERIOD_DAYS) or DEFAULT_INVESTMENT_PERIOD_DAYS)
        projected_net = float(metadata.get("projected_net_profit", 0.0) or 0.0)
        maturity_date = self._format_date_short(str(metadata.get("maturity_at") or ""))

        self.ids.payout_id.text = str(inv_id)
        self.investment_summary = (
            f"Active #{inv_id} | Principal: GHS {amount:,.2f} | Period: {duration}D | "
            f"Projected Net: GHS {projected_net:,.2f} | Locked until {maturity_date}"
        )
        self._set_feedback("Loaded latest active investment.", "success")

    def payout_investment(self):
        investment_id = self._parse_int(self.ids.payout_id.text)
        if investment_id <= 0:
            self._set_feedback("Enter a valid investment ID.", "error")
            self._show_popup("Invalid Investment ID", "Please provide a valid investment ID.")
            return

        self._set_feedback("Checking maturity and processing payout...", "info")
        ok, payload = self._request(
            "POST",
            "/transactions/investment/payout",
            payload={"investment_id": investment_id},
        )
        if ok and isinstance(payload, dict):
            tx_id = int(payload.get("id", 0) or 0)
            principal = float(payload.get("amount", 0.0) or 0.0)
            metadata = self._parse_metadata(payload.get("metadata_json"))
            net_gain = float(metadata.get("gain", 0.0) or 0.0)
            payout_total = principal + net_gain

            msg = (
                f"Investment payout completed.\n"
                f"Principal: GHS {principal:,.2f}\n"
                f"Net profit: GHS {net_gain:,.2f}\n"
                f"Total credited to main balance: GHS {payout_total:,.2f}"
            )
            if tx_id > 0:
                msg = f"{msg}\nPayout Tx: #{tx_id}"

            self.investment_summary = (
                f"Payout completed for investment #{investment_id}. "
                f"Total credited: GHS {payout_total:,.2f}"
            )
            self._set_feedback("Payout successful.", "success")
            self._show_popup("Payout Successful", msg)
            self.load_wallet_balance(notify=False)
            return

        detail = self._extract_detail(payload) or "Unable to process payout."
        detail_lower = detail.lower()
        if "not yet mature" in detail_lower:
            self._set_feedback("Investment is still locked until maturity.", "warning")
            self._show_popup("Still Locked", detail)
            return

        self._set_feedback(detail, "error")
        self._show_popup("Payout Failed", detail)


Builder.load_string(KV)
