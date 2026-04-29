from datetime import datetime, timezone

from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.properties import StringProperty
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel

from core.screen_actions import ActionScreen

KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp
#:set BG (0.043, 0.059, 0.078, 1)
#:set BG_SOFT (0.055, 0.074, 0.096, 1)
#:set CARD (0.075, 0.096, 0.126, 0.98)
#:set CARD2 (0.085, 0.114, 0.142, 0.98)
#:set CARD3 (0.095, 0.126, 0.156, 0.98)
#:set GOLD (0.831, 0.686, 0.216, 1)
#:set GOLD_SOFT (0.93, 0.77, 0.39, 1)
#:set GREEN (0.122, 0.239, 0.169, 1)
#:set GREEN_SOFT (0.18, 0.30, 0.24, 0.96)
#:set RED_SOFT (0.27, 0.16, 0.16, 0.96)
#:set GREEN_CARD (0.18, 0.36, 0.29, 0.95)
#:set SURFACE (0.118, 0.146, 0.176, 0.98)
#:set SURFACE_SOFT (0.085, 0.114, 0.142, 0.98)
#:set TEXT_MAIN (0.96, 0.97, 0.98, 1)
#:set TEXT_SUB (0.69, 0.73, 0.78, 1)
<CardScreen>:
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
                padding: [dp(16 * root.layout_scale), dp(16 * root.layout_scale), dp(16 * root.layout_scale), dp(18 * root.layout_scale)]
                spacing: dp(10 * root.layout_scale)

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(60 * root.layout_scale)

                    Widget:
                        size_hint_x: None
                        width: dp(64 * root.layout_scale)

                    MDLabel:
                        text: "CYBER CASH"
                        halign: "center"
                        theme_text_color: "Custom"
                        text_color: GOLD
                        font_style: "Title"
                        font_size: sp(24 * root.text_scale)
                        bold: True

                    MDTextButton:
                        text: "Back"
                        size_hint_x: None
                        width: dp(64 * root.layout_scale)
                        theme_text_color: "Custom"
                        text_color: GOLD
                        on_release: root.go_back()

                MDBoxLayout:
                    size_hint_y: None
                    height: "1dp"
                    canvas.before:
                        Color:
                            rgba: 0.62, 0.62, 0.64, 0.20
                        Rectangle:
                            pos: self.pos
                            size: self.size
                        Color:
                            rgba: 0.97, 0.82, 0.50, 0.88
                        Rectangle:
                            pos: self.center_x - self.width * 0.18, self.y
                            size: self.width * 0.36, self.height
                        Color:
                            rgba: 0.96, 0.82, 0.48, 0.20
                        Rectangle:
                            pos: self.center_x - self.width * 0.28, self.y - dp(1)
                            size: self.width * 0.56, dp(3)

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(40 * root.layout_scale)
                    spacing: dp(10 * root.layout_scale)

                    MDCard:
                        size_hint: None, None
                        size: dp(34 * root.layout_scale), dp(34 * root.layout_scale)
                        radius: [dp(10 * root.layout_scale)]
                        md_bg_color: [0.64, 0.49, 0.20, 0.36]
                        elevation: 0

                        MDIcon:
                            icon: "credit-card-outline"
                            theme_text_color: "Custom"
                            text_color: GOLD
                            font_size: sp(19 * root.icon_scale)
                            pos_hint: {"center_x": 0.5, "center_y": 0.5}

                    MDLabel:
                        text: root.page_title
                        theme_text_color: "Custom"
                        text_color: TEXT_MAIN
                        font_style: "Title"
                        font_size: sp(17 * root.text_scale)
                        bold: True

                MDLabel:
                    text: root.page_subtitle
                    theme_text_color: "Custom"
                    text_color: TEXT_SUB
                    font_size: sp(12.5 * root.text_scale)
                    adaptive_height: True

                MDCard:
                    radius: [dp(22 * root.layout_scale)]
                    md_bg_color: GREEN_CARD
                    line_color: [0.45, 0.66, 0.56, 0.50]
                    elevation: 0
                    adaptive_height: True
                    padding: [dp(16 * root.layout_scale)] * 4

                    canvas.before:
                        Color:
                            rgba: 0.26, 0.48, 0.38, 0.34
                        RoundedRectangle:
                            pos: self.x + dp(1), self.y + dp(1)
                            size: self.width - dp(2), self.height - dp(2)
                            radius: [dp(20 * root.layout_scale)]
                        Color:
                            rgba: 0.80, 0.96, 0.72, 0.10
                        RoundedRectangle:
                            pos: self.x + dp(14 * root.layout_scale), self.top - self.height * 0.34
                            size: self.width * 0.72, self.height * 0.20
                            radius: [dp(24 * root.layout_scale)]
                        Color:
                            rgba: 0.05, 0.09, 0.10, 0.24
                        RoundedRectangle:
                            pos: self.center_x - dp(6 * root.layout_scale), self.y + dp(10 * root.layout_scale)
                            size: self.width * 0.62, self.height * 0.52
                            radius: [dp(32 * root.layout_scale), dp(12 * root.layout_scale), dp(24 * root.layout_scale), dp(12 * root.layout_scale)]

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(8 * root.layout_scale)
                        adaptive_height: True

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(40 * root.layout_scale)
                            spacing: dp(10 * root.layout_scale)

                            MDCard:
                                size_hint: None, None
                                size: dp(36 * root.layout_scale), dp(36 * root.layout_scale)
                                radius: [dp(10 * root.layout_scale)]
                                md_bg_color: [0.44, 0.66, 0.32, 0.92]
                                elevation: 0

                                MDIcon:
                                    icon: "wallet-outline"
                                    theme_text_color: "Custom"
                                    text_color: [0.94, 1, 0.86, 1]
                                    font_size: sp(19 * root.icon_scale)
                                    pos_hint: {"center_x": 0.5, "center_y": 0.5}

                            MDLabel:
                                text: "Wallet Balance"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_size: sp(15 * root.text_scale)
                                bold: True

                            MDCard:
                                size_hint: None, None
                                size: dp(86 * root.layout_scale), dp(32 * root.layout_scale)
                                radius: [dp(16 * root.layout_scale)]
                                md_bg_color: [0.12, 0.20, 0.17, 0.54]
                                elevation: 0

                                MDLabel:
                                    text: root.card_creation_fee_display
                                    halign: "center"
                                    theme_text_color: "Custom"
                                    text_color: GOLD
                                    font_size: sp(10.5 * root.text_scale)
                                    bold: True

                        MDLabel:
                            text: root.wallet_balance_display
                            theme_text_color: "Custom"
                            text_color: GOLD
                            font_style: "Headline"
                            font_size: sp(28 * root.text_scale)
                            bold: True

                        MDLabel:
                            text: root.wallet_status
                            theme_text_color: "Custom"
                            text_color: 0.80, 0.92, 0.80, 1
                            font_size: sp(12 * root.text_scale)
                            adaptive_height: True

                        MDLabel:
                            text: root.card_fee_hint
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                MDCard:
                    radius: [dp(20 * root.layout_scale)]
                    md_bg_color: SURFACE_SOFT
                    elevation: 0
                    padding: [dp(14 * root.layout_scale)] * 4
                    adaptive_height: True

                    MDBoxLayout:
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: dp(6 * root.layout_scale)

                        MDBoxLayout:
                            orientation: "horizontal"
                            size_hint_y: None
                            height: dp(34 * root.layout_scale)
                            spacing: dp(8 * root.layout_scale)

                            MDLabel:
                                text: "Latest Cards"
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
                                on_release: root.load_cards()

                        MDLabel:
                            text: root.card_summary
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            font_size: sp(12.5 * root.text_scale)
                            adaptive_height: True

                        MDLabel:
                            text: "Your newest cards appear here and the latest card ID fills the manage form after refresh."
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                        MDBoxLayout:
                            id: cards_list
                            orientation: "vertical"
                            adaptive_height: True
                            spacing: dp(8 * root.layout_scale)

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
                            text: "Create Virtual Card"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: GOLD

                        MDLabel:
                            text: "Choose the card currency, pick how the card should behave, and optionally add a spending limit for better control. A flat GHS 25.00 creation fee is charged for every new card."
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(12 * root.text_scale)
                            adaptive_height: True

                        MDLabel:
                            text: "Card Currency"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            adaptive_height: True

                        MDTextField:
                            id: currency_input
                            hint_text: "Currency code, e.g. USD"
                            mode: "outlined"

                        MDLabel:
                            text: "Use a 3-letter currency code such as USD or EUR."
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                        MDLabel:
                            text: "Card Type"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            adaptive_height: True

                        MDTextField:
                            id: type_input
                            hint_text: "Card type: rechargeable or one-time"
                            mode: "outlined"

                        MDLabel:
                            text: "Rechargeable for ongoing use, one-time for single purchases."
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                        MDLabel:
                            text: "Spending Limit"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            adaptive_height: True

                        MDTextField:
                            id: spending_limit_input
                            hint_text: "Optional limit, e.g. 100"
                            mode: "outlined"
                            input_filter: "float"

                        MDLabel:
                            text: "Use rechargeable for repeat payments. Use one-time for a single safer online payment."
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                        MDRaisedButton:
                            text: "Create Card"
                            size_hint_y: None
                            height: dp(48 * root.layout_scale)
                            md_bg_color: GOLD_SOFT
                            text_color: BG
                            on_release: root.create_card()

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
                            text: "Manage Existing Card"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: GOLD

                        MDLabel:
                            text: "Use the latest card ID below, or refresh the cards list above if you need the newest one."
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(12 * root.text_scale)
                            adaptive_height: True

                        MDLabel:
                            text: "Card ID"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            adaptive_height: True

                        MDTextField:
                            id: status_card_id
                            hint_text: "Card ID"
                            mode: "outlined"
                            input_filter: "int"

                        MDLabel:
                            text: "Refresh the cards list above to auto-fill the latest card ID."
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                        MDLabel:
                            text: "Card Status"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            adaptive_height: True

                        MDTextField:
                            id: status_input
                            hint_text: "Status: active or blocked"
                            mode: "outlined"

                        MDLabel:
                            text: "Accepted values: active to unfreeze, blocked to freeze."
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                        MDRaisedButton:
                            text: "Update Status"
                            size_hint_y: None
                            height: dp(46 * root.layout_scale)
                            md_bg_color: [0.24, 0.43, 0.34, 0.96]
                            text_color: TEXT_MAIN
                            on_release: root.update_card_status()

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
            active_target: "cards"
            layout_scale: root.layout_scale
            text_scale: root.text_scale
            icon_scale: root.icon_scale
"""


class CardScreen(ActionScreen):
    CARD_CREATION_FEE_GHS = 25.0
    page_title = StringProperty("Virtual Cards")
    page_subtitle = StringProperty("Create, review, freeze, and unfreeze your virtual cards from one secure dashboard.")
    wallet_balance_display = StringProperty("GHS 0.00")
    wallet_status = StringProperty("Pulling live wallet...")
    card_creation_fee_display = StringProperty("Fee: GHS 25")
    card_fee_hint = StringProperty("A flat GHS 25.00 fee applies to each new virtual card.")
    card_summary = StringProperty(
        "Load cards to see your latest card, current status, spending limit, and balance."
    )
    feedback_hint = StringProperty("")

    def on_pre_enter(self):
        self.load_wallet_balance(notify=False, show_popup=False)
        self.load_cards(notify=False, show_popup=False)

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
    def _friendly_card_error(detail: str) -> str:
        message = str(detail or "").strip()
        normalized = message.lower()
        if "not found" in normalized:
            return "We could not find that virtual card. Refresh your cards and try again."
        if "status" in normalized and "active" in normalized and "blocked" in normalized:
            return "Card status must be active or blocked."
        if "ghs 25.00 is required to create a new virtual card" in normalized:
            return "You need at least GHS 25.00 in your wallet to create a new virtual card."
        if "insufficient" in normalized:
            return "Your wallet balance is too low. Keep at least GHS 25.00 available to create a new virtual card."
        return message or "Unable to complete this card action right now."

    @staticmethod
    def _friendly_time(timestamp: str) -> str:
        raw = str(timestamp or "").strip()
        if not raw:
            return "Recent"
        try:
            dt_value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            day = dt_value.astimezone(timezone.utc).date()
            if day == now.date():
                return dt_value.strftime("Today %H:%M")
            if (now.date() - day).days == 1:
                return dt_value.strftime("Yesterday %H:%M")
            return dt_value.strftime("%d %b %H:%M")
        except Exception:
            return "Recent"

    @staticmethod
    def _mask_card_number(card_number: str) -> str:
        raw = str(card_number or "").strip()
        digits = "".join(ch for ch in raw if ch.isdigit())
        if len(digits) >= 4:
            return f"**** **** **** {digits[-4:]}"
        if len(raw) > 4:
            return f"**** {raw[-4:]}"
        return raw or "Unknown card"

    @staticmethod
    def _card_status_style(status: str) -> tuple[str, list[float]]:
        normalized = str(status or "").strip().lower()
        if normalized == "active":
            return "ACTIVE", [0.54, 0.82, 0.67, 1]
        if normalized in {"blocked", "frozen"}:
            return "BLOCKED", [0.96, 0.47, 0.42, 1]
        return (normalized.replace("_", " ").upper() or "PENDING"), [0.94, 0.79, 0.46, 1]

    def _build_card_item(self, card: dict) -> MDCard:
        layout_scale = float(self.layout_scale or 1.0)
        text_scale = float(self.text_scale or 1.0)
        card_number = self._mask_card_number(str(card.get("card_number", "") or ""))
        currency = str(card.get("currency", "USD") or "USD").strip().upper()
        card_type = str(card.get("type", "rechargeable") or "rechargeable").strip().replace("-", " ").title()
        balance = float(card.get("balance", 0.0) or 0.0)
        limit = float(card.get("spending_limit", 0.0) or 0.0)
        expiry = str(card.get("expiry_date", "") or "").strip()
        created_text = self._friendly_time(str(card.get("created_at", "") or ""))
        status_label, status_color = self._card_status_style(str(card.get("status", "") or ""))
        limit_text = f"{currency} {limit:,.2f}" if limit > 0 else "No spending limit"
        expiry_text = f"Expires {expiry}" if expiry else "Expiry pending"

        card_widget = MDCard(
            size_hint_y=None,
            height=dp(108 * layout_scale),
            radius=[dp(16 * layout_scale)],
            md_bg_color=[0.10, 0.12, 0.15, 0.96],
            line_color=[0.24, 0.28, 0.24, 0.42],
            elevation=0,
            padding=[dp(12 * layout_scale), dp(10 * layout_scale), dp(12 * layout_scale), dp(10 * layout_scale)],
        )
        row = MDBoxLayout(orientation="horizontal", spacing=dp(10 * layout_scale))

        indicator = MDCard(
            size_hint=(None, None),
            size=(dp(72 * layout_scale), dp(44 * layout_scale)),
            radius=[dp(12 * layout_scale)],
            md_bg_color=[status_color[0], status_color[1], status_color[2], 0.20],
            line_color=status_color,
            elevation=0,
        )
        indicator.add_widget(
            MDLabel(
                text=status_label,
                halign="center",
                valign="middle",
                text_size=indicator.size,
                theme_text_color="Custom",
                text_color=status_color,
                bold=True,
                font_size=f"{10.5 * text_scale:.1f}sp",
            )
        )

        meta = MDBoxLayout(orientation="vertical", spacing=dp(2 * layout_scale))
        meta.add_widget(
            MDLabel(
                text=f"Card {card_number}",
                theme_text_color="Custom",
                text_color=[0.96, 0.97, 0.98, 1],
                bold=True,
                font_size=f"{14 * text_scale:.1f}sp",
                size_hint_y=None,
                height=dp(20 * layout_scale),
            )
        )
        meta.add_widget(
            MDLabel(
                text=f"{currency} | {card_type}",
                theme_text_color="Custom",
                text_color=[0.72, 0.76, 0.81, 1],
                font_size=f"{11 * text_scale:.1f}sp",
                size_hint_y=None,
                height=dp(18 * layout_scale),
            )
        )
        meta.add_widget(
            MDLabel(
                text=f"Balance: {currency} {balance:,.2f}",
                theme_text_color="Custom",
                text_color=[0.94, 0.79, 0.46, 1],
                font_size=f"{11 * text_scale:.1f}sp",
                size_hint_y=None,
                height=dp(18 * layout_scale),
            )
        )
        meta.add_widget(
            MDLabel(
                text=f"Limit: {limit_text}",
                theme_text_color="Custom",
                text_color=[0.72, 0.76, 0.81, 1],
                font_size=f"{10.5 * text_scale:.1f}sp",
                size_hint_y=None,
                height=dp(18 * layout_scale),
            )
        )

        side = MDBoxLayout(orientation="vertical", spacing=dp(2 * layout_scale), size_hint_x=None, width=dp(112 * layout_scale))
        side.add_widget(
            MDLabel(
                text=expiry_text,
                halign="right",
                theme_text_color="Custom",
                text_color=[0.96, 0.97, 0.98, 1],
                font_size=f"{11 * text_scale:.1f}sp",
                size_hint_y=None,
                height=dp(18 * layout_scale),
            )
        )
        side.add_widget(
            MDLabel(
                text=f"Created {created_text}",
                halign="right",
                theme_text_color="Custom",
                text_color=[0.72, 0.76, 0.81, 1],
                font_size=f"{10.5 * text_scale:.1f}sp",
                size_hint_y=None,
                height=dp(18 * layout_scale),
            )
        )

        row.add_widget(indicator)
        row.add_widget(meta)
        row.add_widget(side)
        card_widget.add_widget(row)
        return card_widget

    def _render_cards(self, cards: list[dict]) -> None:
        container = self.ids.cards_list
        container.clear_widgets()
        layout_scale = float(self.layout_scale or 1.0)
        text_scale = float(self.text_scale or 1.0)

        if not cards:
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
                    text="No virtual cards yet. Create your first card below to start safer online payments.",
                    halign="center",
                    theme_text_color="Custom",
                    text_color=[0.72, 0.76, 0.81, 1],
                    font_size=f"{11.5 * text_scale:.1f}sp",
                )
            )
            container.add_widget(empty_card)
            return

        for card in cards[:5]:
            container.add_widget(self._build_card_item(card))

    def load_wallet_balance(self, notify: bool = False, show_popup: bool = False):
        ok, payload = self._request("GET", "/wallet/me")
        if ok and isinstance(payload, dict):
            balance = float(payload.get("balance", 0.0) or 0.0)
            self.wallet_balance_display = f"GHS {balance:,.2f}"
            self.wallet_status = "Live wallet balance"
            if notify:
                self._set_feedback("Wallet updated.", "success")
                self.feedback_hint = "Keep at least GHS 25.00 available before creating a new virtual card."
            return

        detail = self._friendly_card_error(self._extract_detail(payload) or "Unable to load wallet balance.")
        self.wallet_status = "Wallet sync unavailable"
        if notify:
            self._set_feedback(detail, "error")
            self.feedback_hint = "Refresh the wallet balance before creating or managing cards."
        if show_popup:
            self._show_popup("Wallet Sync Error", detail)

    def create_card(self):
        currency = str(self.ids.currency_input.text or "").strip().upper() or "USD"
        card_type = str(self.ids.type_input.text or "").strip().lower() or "rechargeable"
        spending_limit = self._parse_float(self.ids.spending_limit_input.text)
        if card_type not in {"rechargeable", "one-time"}:
            self._set_feedback("Card type must be rechargeable or one-time.", "error")
            self.feedback_hint = "Use rechargeable for ongoing payments or one-time for a single-use virtual card."
            self._show_popup("Invalid Card Type", "Use rechargeable or one-time.")
            return

        self._set_feedback("Creating your virtual card...", "info")
        self.feedback_hint = "GHS 25.00 will be deducted from your wallet when the virtual card is created."
        ok, payload = self._request(
            "POST",
            "/virtualcards/request",
            payload={
                "currency": currency,
                "type": card_type,
                "spending_limit": max(spending_limit, 0.0),
            },
        )
        if ok and isinstance(payload, dict):
            card_id = payload.get("id")
            status = str(payload.get("status", "active")).strip().lower()
            type_text = "One-Time" if card_type == "one-time" else "Rechargeable"
            limit_text = (
                f" Spending limit: {currency} {spending_limit:,.2f}."
                if spending_limit > 0
                else " No spending limit set."
            )
            self.card_summary = (
                f"Card #{card_id} created successfully. "
                f"Status: {status.title()}. Currency: {currency}. Type: {type_text}.{limit_text} "
                f"Creation fee charged: GHS {self.CARD_CREATION_FEE_GHS:,.2f}."
            )
            if card_id:
                self.ids.status_card_id.text = str(card_id)
            self.ids.status_input.text = status
            self._set_feedback("Virtual card created successfully.", "success")
            self.feedback_hint = "Your new card ID has been filled into the manage form below, and your wallet balance has been refreshed."
            self.load_wallet_balance(notify=False, show_popup=False)
            self.load_cards(notify=False, show_popup=False)
            self._show_popup(
                "Card Created",
                f"Virtual card #{card_id} created successfully. GHS {self.CARD_CREATION_FEE_GHS:,.2f} was charged from your wallet.",
            )
            return

        detail = self._friendly_card_error(self._extract_detail(payload) or "Unable to create virtual card.")
        self._set_feedback(detail, "error")
        self.feedback_hint = "Review the currency, card type, optional spending limit, and make sure your wallet has at least GHS 25.00."
        self._show_popup("Card Creation Failed", detail)

    def load_cards(self, notify: bool = True, show_popup: bool = True):
        if notify:
            self._set_feedback("Loading your cards...", "info")
            self.feedback_hint = "This checks your latest virtual cards and fills the manage form automatically."
        ok, payload = self._request("GET", "/virtualcards/me")
        if ok and isinstance(payload, list):
            if not payload:
                self.card_summary = "No virtual cards found yet. Create your first virtual card in the section below to start safer online payments."
                self._render_cards([])
                if notify:
                    self._set_feedback("No cards found.", "warning")
                self.feedback_hint = "Choose a card type above and tap Create Card to get started. The creation fee is GHS 25.00."
                return
            sorted_cards = sorted(payload, key=lambda item: str(item.get("created_at", "") or ""), reverse=True)
            latest = sorted_cards[0]
            card_id = latest.get("id")
            status = str(latest.get("status", "unknown")).strip().title()
            balance = float(latest.get("balance", 0.0) or 0.0)
            currency = str(latest.get("currency", "USD") or "USD").strip().upper()
            card_type = str(latest.get("type", "rechargeable") or "rechargeable").strip().replace("-", " ").title()
            spending_limit = float(latest.get("spending_limit", 0.0) or 0.0)
            limit_text = (
                f" Spending limit: {currency} {spending_limit:,.2f}."
                if spending_limit > 0
                else " No spending limit set."
            )
            self.card_summary = (
                f"{len(payload)} virtual card(s). "
                f"Latest card #{card_id} is {status}, {card_type}, {currency}, with balance {balance:,.2f}.{limit_text}"
            )
            if card_id:
                self.ids.status_card_id.text = str(card_id)
            self.ids.status_input.text = status.lower()
            self._render_cards(sorted_cards)
            if notify:
                self._set_feedback("Cards loaded successfully.", "success")
            self.feedback_hint = "The latest card ID and current status have been filled into the manage form for you."
            return

        detail = self._friendly_card_error(self._extract_detail(payload) or "Unable to load cards.")
        self.card_summary = "Card dashboard unavailable right now."
        self._render_cards([])
        if notify:
            self._set_feedback(detail, "error")
        self.feedback_hint = "Please refresh the cards dashboard when your connection is stable."
        if show_popup:
            self._show_popup("Card Sync Error", detail)

    def update_card_status(self):
        card_id = self._parse_int(self.ids.status_card_id.text)
        status_value = str(self.ids.status_input.text or "").strip().lower()
        if card_id <= 0:
            self._set_feedback("Enter a valid card ID.", "error")
            self.feedback_hint = "Use the Refresh button in Latest Cards first if you want the latest card ID filled in automatically."
            self._show_popup("Invalid Card ID", "Card ID must be a positive number.")
            return
        if status_value not in {"active", "blocked"}:
            self._set_feedback("Status must be active or blocked.", "error")
            self.feedback_hint = "Use active to unfreeze a card or blocked to freeze it."
            self._show_popup("Invalid Status", "Use active or blocked.")
            return

        self._set_feedback("Updating card status...", "info")
        self.feedback_hint = "The selected virtual card will be updated as soon as the request completes."
        ok, payload = self._request(
            "PATCH",
            f"/virtualcards/{card_id}/status",
            payload={"status": status_value},
        )
        if ok and isinstance(payload, dict):
            status = str(payload.get("status", status_value)).strip().title()
            self.ids.status_input.text = status.lower()
            self.card_summary = f"Card #{card_id} is now {status}. You can refresh cards to pull the latest balance and card details."
            self._set_feedback("Card status updated successfully.", "success")
            self.feedback_hint = "Use active to unfreeze later or blocked to freeze the card again."
            self.load_cards(notify=False, show_popup=False)
            self._show_popup("Status Updated", f"Card #{card_id} is now {status}.")
            return

        detail = self._friendly_card_error(self._extract_detail(payload) or "Unable to update card status.")
        self._set_feedback(detail, "error")
        self.feedback_hint = "Refresh your cards first if you are not sure which card ID to update."
        self._show_popup("Status Update Failed", detail)


Builder.load_string(KV)
