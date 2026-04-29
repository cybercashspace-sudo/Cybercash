from __future__ import annotations

from datetime import datetime

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import StringProperty

from core.screen_actions import ActionScreen
from utils.network import normalize_ghana_number

MIN_ESCROW_DEAL_GHS = 20.0
ESCROW_CREATE_FEE_GHS = 5.0
ESCROW_RELEASE_FEE_GHS = 5.0

DEFAULT_ESCROW_SUBTITLE = (
    "Protect buyer and seller payments. Funds stay locked until you confirm release."
)
DEFAULT_ESCROW_SUMMARY = (
    "No escrow deals yet. Create your first protected deal below and refresh to track its status."
)
DEFAULT_LATEST_DEAL_TITLE = "No recent escrow deal selected"
DEFAULT_LATEST_DEAL_SUBTITLE = (
    "Your latest deal summary will appear here after you create or refresh deals."
)
DEFAULT_ESCROW_FEEDBACK = (
    "Use escrow when you want to hold funds safely until delivery, service, or inspection is complete."
)

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
<EscrowScreen>:
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
                        text: root.page_title
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
                    height: dp(152 * root.layout_scale)
                    padding: [dp(14 * root.layout_scale)] * 4

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(4 * root.layout_scale)

                        MDLabel:
                            text: "Funds currently protected in escrow"
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN

                        MDLabel:
                            text: root.held_balance_display
                            font_style: "Headline"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: GOLD
                            font_size: sp(28 * root.text_scale)

                        MDLabel:
                            text: root.deal_status_text
                            theme_text_color: "Custom"
                            text_color: [0.80, 0.92, 0.80, 1]
                            font_size: sp(12 * root.text_scale)

                        MDLabel:
                            text: root.latest_deal_title
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            bold: True
                            font_size: sp(12.5 * root.text_scale)
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
                            text: "Escrow overview"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: GOLD

                        MDLabel:
                            text: root.escrow_summary
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            font_size: sp(12.5 * root.text_scale)
                            adaptive_height: True

                        MDLabel:
                            text: root.latest_deal_subtitle
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(12 * root.text_scale)
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
                        spacing: dp(9 * root.layout_scale)

                        MDLabel:
                            text: "Start a protected escrow deal"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: GOLD

                        MDLabel:
                            text: root.fee_note_text
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(12 * root.text_scale)
                            adaptive_height: True

                        MDTextField:
                            id: recipient_wallet_id
                            hint_text: "Recipient MoMo number"
                            mode: "outlined"

                        MDLabel:
                            text: "Use the verified Ghana MoMo number of the person who should receive the escrow funds."
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                        MDTextField:
                            id: escrow_amount
                            hint_text: "Escrow amount in GHS"
                            mode: "outlined"
                            input_filter: "float"

                        MDLabel:
                            text: "Minimum protected deal amount is GHS 20.00."
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                        MDTextField:
                            id: escrow_description
                            hint_text: "Deal note or delivery summary"
                            mode: "outlined"

                        MDLabel:
                            text: "Example: iPhone 13 delivery after inspection."
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                        MDLabel:
                            text: root.release_note_text
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(12 * root.text_scale)
                            adaptive_height: True

                        MDFillRoundFlatIconButton:
                            text: "Create Escrow Deal"
                            icon: "shield-lock-outline"
                            md_bg_color: GOLD_SOFT
                            text_color: BG
                            size_hint_y: None
                            height: dp(50 * root.layout_scale)
                            on_release: root.create_escrow()

                MDCard:
                    radius: [dp(20 * root.layout_scale)]
                    md_bg_color: SURFACE
                    elevation: 0
                    padding: [dp(14 * root.layout_scale)] * 4
                    adaptive_height: True

                    MDBoxLayout:
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: dp(9 * root.layout_scale)

                        MDLabel:
                            text: "Review or release a deal"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: GOLD

                        MDLabel:
                            text: "Refresh your escrow history, then enter a deal ID when you are ready to release funds."
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(12 * root.text_scale)
                            adaptive_height: True

                        MDTextField:
                            id: release_deal_id
                            hint_text: "Deal ID to release"
                            mode: "outlined"
                            input_filter: "int"

                        MDLabel:
                            text: "We auto-fill the latest deal ID after you refresh or create a new deal when available."
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                        MDGridLayout:
                            cols: 1 if root.compact_mode else 2
                            spacing: dp(8 * root.layout_scale)
                            adaptive_height: True
                            size_hint_y: None
                            height: self.minimum_height

                            MDFillRoundFlatIconButton:
                                text: "Refresh My Deals"
                                icon: "refresh"
                                md_bg_color: SURFACE_SOFT
                                text_color: TEXT_MAIN
                                size_hint_y: None
                                height: dp(48 * root.layout_scale)
                                on_release: root.load_deals()

                            MDFillRoundFlatIconButton:
                                text: "Release Selected Deal"
                                icon: "check-decagram-outline"
                                md_bg_color: GOLD_SOFT
                                text_color: BG
                                size_hint_y: None
                                height: dp(48 * root.layout_scale)
                                on_release: root.release_escrow()

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
            active_target: "escrow"
            layout_scale: root.layout_scale
            text_scale: root.text_scale
            icon_scale: root.icon_scale
"""


class EscrowScreen(ActionScreen):
    page_title = StringProperty("Escrow Dashboard")
    page_subtitle = StringProperty(DEFAULT_ESCROW_SUBTITLE)
    held_balance_display = StringProperty("GHS 0.00")
    deal_status_text = StringProperty("No active deals yet.")
    fee_note_text = StringProperty(
        "You pay GHS 5.00 when you create a deal. The recipient pays GHS 5.00 only when funds are released."
    )
    release_note_text = StringProperty(
        "Release funds only after you confirm delivery, service completion, or inspection approval."
    )
    latest_deal_title = StringProperty(DEFAULT_LATEST_DEAL_TITLE)
    latest_deal_subtitle = StringProperty(DEFAULT_LATEST_DEAL_SUBTITLE)
    escrow_summary = StringProperty(DEFAULT_ESCROW_SUMMARY)

    def on_enter(self, *_args):
        if not str(self.feedback_text or "").strip():
            self._set_feedback(DEFAULT_ESCROW_FEEDBACK, "info")
        Clock.schedule_once(lambda _dt: self.load_deals(notify_popup=False), 0)

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
    def _format_money(amount: float) -> str:
        return f"GHS {float(amount or 0.0):,.2f}"

    @staticmethod
    def _format_date_label(raw_value: str | None) -> str:
        value = str(raw_value or "").strip()
        if not value:
            return "Date not available"
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.strftime("%d %b %Y")
        except Exception:
            return value

    def _reset_dashboard_copy(self) -> None:
        self.held_balance_display = "GHS 0.00"
        self.deal_status_text = "No active deals yet."
        self.latest_deal_title = DEFAULT_LATEST_DEAL_TITLE
        self.latest_deal_subtitle = DEFAULT_LATEST_DEAL_SUBTITLE
        self.escrow_summary = DEFAULT_ESCROW_SUMMARY
        if "release_deal_id" in self.ids:
            self.ids.release_deal_id.text = ""

    @staticmethod
    def _friendly_escrow_error(detail: str) -> str:
        message = str(detail or "").strip()
        normalized = message.lower()
        if "please sign in to continue" in normalized:
            return "Please sign in before creating or managing escrow deals."
        if "recipient_wallet_id" in normalized and "required" in normalized:
            return "Recipient MoMo number is required."
        if "recipient_wallet_id" in normalized and "valid 10-digit registered number" in normalized:
            return "Enter a valid 10-digit verified Ghana MoMo number."
        if "recipient not found" in normalized:
            return "Recipient not found. Use an active verified MoMo number."
        if "minimum escrow deal amount is ghs 20.00" in normalized:
            return "Minimum escrow deal amount is GHS 20.00."
        if "deal amount must exceed ghs" in normalized:
            return "Increase the deal amount so the recipient still receives a positive payout after the release fee."
        if "different user" in normalized:
            return "You cannot open escrow with your own MoMo number."
        if "insufficient available balance" in normalized or "insufficient balance" in normalized:
            return "Insufficient balance. You need the deal amount plus the fixed GHS 5.00 creation fee."
        if "deal already released" in normalized:
            return "This escrow deal was already released."
        if "under dispute" in normalized:
            return "This escrow deal is under dispute and cannot be released right now."
        if "deal not found" in normalized:
            return "We could not find that escrow deal. Refresh your list and try again."
        return message or "Unable to process the escrow request right now."

    def _apply_deal_snapshot(self, deals: list[dict]) -> None:
        if not deals:
            self._reset_dashboard_copy()
            return

        active_deals = []
        released_deals = []
        disputed_deals = []
        for deal in deals:
            status_value = str(deal.get("status", "active") or "active").strip().lower()
            if status_value == "released":
                released_deals.append(deal)
            elif status_value == "disputed":
                disputed_deals.append(deal)
            else:
                active_deals.append(deal)

        held_total = sum(float(item.get("amount", 0.0) or 0.0) for item in active_deals)
        self.held_balance_display = self._format_money(held_total)
        self.deal_status_text = (
            f"{len(active_deals)} active, {len(released_deals)} released, {len(disputed_deals)} disputed."
        )

        latest = deals[0]
        latest_id = int(latest.get("deal_id", 0) or 0)
        latest_status = str(latest.get("status", "active") or "active").strip().title()
        latest_amount = float(latest.get("amount", 0.0) or 0.0)
        latest_net = float(latest.get("receiver_net_amount", 0.0) or 0.0)
        latest_recipient = str(latest.get("recipient_wallet_id") or "N/A")
        latest_description = str(latest.get("description") or "").strip() or "Protected payment"
        latest_date = self._format_date_label(latest.get("created_at"))

        self.latest_deal_title = f"Latest deal #{latest_id if latest_id > 0 else '-'} • {latest_status}"
        self.latest_deal_subtitle = (
            f"{latest_description}. Recipient: {latest_recipient}. "
            f"Deal value: {self._format_money(latest_amount)}. "
            f"Recipient net on release: {self._format_money(latest_net)}. "
            f"Created: {latest_date}."
        )
        self.escrow_summary = (
            f"You have {len(deals)} escrow deal(s) on record. "
            f"Funds currently protected in active deals: {self._format_money(held_total)}."
        )
        if latest_id > 0:
            self.ids.release_deal_id.text = str(latest_id)

    def create_escrow(self):
        recipient_wallet_id = normalize_ghana_number(self.ids.recipient_wallet_id.text.strip())
        amount = self._parse_float(self.ids.escrow_amount.text)
        description = str(self.ids.escrow_description.text or "").strip()

        if not recipient_wallet_id or len(recipient_wallet_id) != 10 or not recipient_wallet_id.isdigit():
            self._set_feedback("Enter a valid 10-digit verified Ghana MoMo number.", "error")
            self._show_popup("Invalid Recipient", "Please enter a valid 10-digit verified Ghana MoMo number.")
            return
        if amount < MIN_ESCROW_DEAL_GHS:
            self._set_feedback("Enter an escrow amount of at least GHS 20.00.", "error")
            self._show_popup("Invalid Amount", f"Minimum escrow deal amount is {self._format_money(MIN_ESCROW_DEAL_GHS)}.")
            return

        create_fee = ESCROW_CREATE_FEE_GHS
        release_fee = ESCROW_RELEASE_FEE_GHS
        total_debit = round(amount + create_fee, 2)
        receiver_net = max(round(amount - release_fee, 2), 0.0)
        self._set_feedback(
            (
                f"Creating escrow deal. Total debit now: {self._format_money(total_debit)}. "
                f"Recipient will receive {self._format_money(receiver_net)} after the release fee."
            ),
            "info",
        )

        ok, payload = self._request(
            "POST",
            "/transactions/escrow/create",
            payload={
                "recipient_wallet_id": recipient_wallet_id,
                "amount": amount,
                "description": description or None,
            },
        )
        if ok and isinstance(payload, dict):
            deal_id = int(payload.get("id", 0) or 0)
            message = (
                f"Escrow deal created successfully.\n"
                f"Amount protected: {self._format_money(amount)}\n"
                f"Creation fee charged now: {self._format_money(create_fee)}\n"
                f"Recipient net on release: {self._format_money(receiver_net)}"
            )
            if deal_id > 0:
                message = f"Deal #{deal_id} created successfully.\n{message.splitlines()[1]}\n{message.splitlines()[2]}\n{message.splitlines()[3]}"
                self.ids.release_deal_id.text = str(deal_id)
            self.ids.escrow_amount.text = ""
            self.ids.escrow_description.text = ""
            self._set_feedback("Escrow deal created successfully.", "success")
            self._show_popup("Escrow Created", message)
            self.load_deals(notify_popup=False)
            return

        detail = self._extract_detail(payload)
        friendly = self._friendly_escrow_error(detail)
        self._set_feedback(friendly, "error")
        self._show_popup("Escrow Creation Failed", friendly)

    def load_deals(self, notify_popup: bool = True):
        self._set_feedback("Refreshing escrow dashboard...", "info")
        ok, payload = self._request("GET", "/transactions/escrow/deals")
        if ok and isinstance(payload, list):
            self._apply_deal_snapshot(payload)
            if not payload:
                self._set_feedback("No escrow deals found yet.", "warning")
                return
            self._set_feedback("Escrow dashboard updated.", "success")
            return

        detail = self._extract_detail(payload) or "Unable to load escrow deals."
        friendly = self._friendly_escrow_error(detail)
        self._set_feedback(friendly, "error")
        if notify_popup:
            self._show_popup("Escrow Sync Error", friendly)

    def release_escrow(self):
        deal_id = self._parse_int(self.ids.release_deal_id.text)
        if deal_id <= 0:
            self._set_feedback("Enter a valid escrow deal ID before release.", "error")
            self._show_popup("Invalid Deal ID", "Please enter a valid escrow deal ID before releasing funds.")
            return

        self._set_feedback("Releasing escrow funds...", "info")
        ok, payload = self._request("POST", f"/transactions/escrow/{deal_id}/release")
        if ok and isinstance(payload, dict):
            release_id = int(payload.get("id", 0) or 0)
            message = (
                f"Escrow deal #{deal_id} released successfully.\n"
                f"Recipient release fee charged: {self._format_money(ESCROW_RELEASE_FEE_GHS)}"
            )
            if release_id > 0:
                message = (
                    f"Escrow released successfully.\n"
                    f"Release transaction: #{release_id}\n"
                    f"Recipient release fee charged: {self._format_money(ESCROW_RELEASE_FEE_GHS)}"
                )
            self._set_feedback("Escrow release completed.", "success")
            self._show_popup("Escrow Released", message)
            self.load_deals(notify_popup=False)
            return

        detail = self._extract_detail(payload)
        friendly = self._friendly_escrow_error(detail)
        self._set_feedback(friendly, "error")
        self._show_popup("Escrow Release Failed", friendly)


Builder.load_string(KV)
