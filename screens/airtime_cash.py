from kivy.lang import Builder
from kivy.properties import NumericProperty, StringProperty

from core.screen_actions import ActionScreen
from utils.network import detect_network, normalize_ghana_number

DEFAULT_PAYOUT_RATE = 0.8
MERCHANT_NUMBERS = {
    "MTN": "0559000000",
    "TELECEL": "0209000000",
    "AIRTELTIGO": "0279000000",
    "DEFAULT": "0559000000",
}

KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp
#:set BG (0.03, 0.04, 0.06, 1)
#:set SURFACE (0.08, 0.10, 0.14, 0.95)
#:set SURFACE_SOFT (0.12, 0.14, 0.18, 0.95)
#:set GOLD (0.94, 0.79, 0.46, 1)
#:set GOLD_SOFT (0.93, 0.77, 0.39, 1)
#:set TEXT_MAIN (0.95, 0.95, 0.95, 1)
#:set TEXT_SUB (0.74, 0.76, 0.80, 1)
<AirtimeCashScreen>:
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
                        text: "Airtime 2 Cash"
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
                    text: "Sell airtime and receive Mobile Money payout after verification."
                    theme_text_color: "Custom"
                    text_color: TEXT_SUB
                    font_size: sp(12.5 * root.text_scale)
                    adaptive_height: True

                MDCard:
                    radius: [dp(18 * root.layout_scale)]
                    md_bg_color: SURFACE_SOFT
                    elevation: 0
                    padding: [dp(12 * root.layout_scale)] * 4
                    adaptive_height: True

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(6 * root.layout_scale)
                        adaptive_height: True

                        MDLabel:
                            text: "How it works"
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            font_size: sp(13 * root.text_scale)
                            bold: True

                        MDLabel:
                            text: "1. Generate a merchant number"
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                        MDLabel:
                            text: "2. Send airtime from your line"
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                        MDLabel:
                            text: "3. Tap 'I Have Sent Airtime' and wait for verification"
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                        MDLabel:
                            text: "Payout is sent to your MoMo after verification."
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11 * root.text_scale)
                            adaptive_height: True

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
                            text: "Your phone number"
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            font_size: sp(13 * root.text_scale)

                        MDTextField:
                            id: phone_input
                            hint_text: "Phone number, e.g. 0241234567"
                            mode: "outlined"
                            on_text: root.on_phone_change(self.text)

                        MDLabel:
                            text: root.network_helper_text
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11 * root.text_scale)
                            adaptive_height: True

                        MDLabel:
                            text: "Select network"
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            font_size: sp(13 * root.text_scale)

                        MDGridLayout:
                            cols: 1 if root.compact_mode else 3
                            adaptive_height: True
                            row_default_height: dp(48 * root.layout_scale)
                            row_force_default: True
                            spacing: dp(10 * root.layout_scale)

                            MDCard:
                                radius: [dp(14 * root.layout_scale)]
                                md_bg_color: GOLD_SOFT if root.is_network_selected("MTN") else SURFACE_SOFT
                                line_color: [0.56, 0.78, 0.68, 0.45] if root.is_network_selected("MTN") else [0.24, 0.28, 0.32, 0.5]
                                elevation: 0
                                padding: [dp(10 * root.layout_scale), 0, dp(10 * root.layout_scale), 0]
                                on_release: root.select_network("MTN")

                                MDLabel:
                                    text: "MTN"
                                    halign: "center"
                                    valign: "middle"
                                    theme_text_color: "Custom"
                                    text_color: BG if root.is_network_selected("MTN") else TEXT_MAIN
                                    font_size: sp(13 * root.text_scale)
                                    bold: True

                            MDCard:
                                radius: [dp(14 * root.layout_scale)]
                                md_bg_color: GOLD_SOFT if root.is_network_selected("TELECEL") else SURFACE_SOFT
                                line_color: [0.62, 0.52, 0.30, 0.45] if root.is_network_selected("TELECEL") else [0.24, 0.28, 0.32, 0.5]
                                elevation: 0
                                padding: [dp(10 * root.layout_scale), 0, dp(10 * root.layout_scale), 0]
                                on_release: root.select_network("TELECEL")

                                MDLabel:
                                    text: "Telecel"
                                    halign: "center"
                                    valign: "middle"
                                    theme_text_color: "Custom"
                                    text_color: BG if root.is_network_selected("TELECEL") else TEXT_MAIN
                                    font_size: sp(13 * root.text_scale)
                                    bold: True

                            MDCard:
                                radius: [dp(14 * root.layout_scale)]
                                md_bg_color: GOLD_SOFT if root.is_network_selected("AIRTELTIGO") else SURFACE_SOFT
                                line_color: [0.48, 0.66, 0.86, 0.45] if root.is_network_selected("AIRTELTIGO") else [0.24, 0.28, 0.32, 0.5]
                                elevation: 0
                                padding: [dp(10 * root.layout_scale), 0, dp(10 * root.layout_scale), 0]
                                on_release: root.select_network("AIRTELTIGO")

                                MDLabel:
                                    text: "AirtelTigo"
                                    halign: "center"
                                    valign: "middle"
                                    theme_text_color: "Custom"
                                    text_color: BG if root.is_network_selected("AIRTELTIGO") else TEXT_MAIN
                                    font_size: sp(13 * root.text_scale)
                                    bold: True

                        MDTextField:
                            id: network_input
                            hint_text: "Network (auto)"
                            mode: "outlined"
                            on_text: root.on_manual_network(self.text)

                        MDLabel:
                            text: "Airtime amount"
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            font_size: sp(13 * root.text_scale)

                        MDTextField:
                            id: amount_input
                            hint_text: "Amount in GHS"
                            mode: "outlined"
                            input_filter: "float"
                            on_text: root.on_amount_change(self.text)

                        MDCard:
                            radius: [dp(16 * root.layout_scale)]
                            md_bg_color: SURFACE_SOFT
                            elevation: 0
                            padding: [dp(12 * root.layout_scale)] * 4
                            adaptive_height: True

                            MDBoxLayout:
                                orientation: "vertical"
                                spacing: dp(4 * root.layout_scale)
                                adaptive_height: True

                                MDLabel:
                                    text: "Estimated cash payout"
                                    theme_text_color: "Custom"
                                    text_color: TEXT_SUB
                                    font_size: sp(11.5 * root.text_scale)
                                    adaptive_height: True

                                MDLabel:
                                    text: root.payout_estimate
                                    theme_text_color: "Custom"
                                    text_color: GOLD
                                    font_size: sp(18 * root.text_scale)
                                    bold: True

                                MDLabel:
                                    text: "Platform fee: " + root.fee_estimate
                                    theme_text_color: "Custom"
                                    text_color: TEXT_SUB
                                    font_size: sp(11.5 * root.text_scale)
                                    adaptive_height: True

                                MDLabel:
                                    text: root.rate_hint
                                    theme_text_color: "Custom"
                                    text_color: TEXT_SUB
                                    font_size: sp(11 * root.text_scale)
                                    adaptive_height: True

                                MDLabel:
                                    text: "Large amounts may require manual review before payout."
                                    theme_text_color: "Custom"
                                    text_color: TEXT_SUB
                                    font_size: sp(10.5 * root.text_scale)
                                    adaptive_height: True

                        MDGridLayout:
                            cols: 1 if root.compact_mode else 2
                            adaptive_height: True
                            row_default_height: dp(52 * root.layout_scale)
                            row_force_default: True
                            spacing: dp(10 * root.layout_scale)

                            MDFillRoundFlatIconButton:
                                text: "Generate Merchant Number"
                                icon: "phone-forward"
                                md_bg_color: GOLD_SOFT
                                text_color: BG
                                on_release: root.generate_merchant_number()

                            MDFillRoundFlatIconButton:
                                text: "I Have Sent Airtime"
                                icon: "check-circle-outline"
                                md_bg_color: SURFACE_SOFT
                                text_color: TEXT_MAIN
                                on_release: root.confirm_transfer()

                MDCard:
                    radius: [dp(20 * root.layout_scale)]
                    md_bg_color: SURFACE_SOFT
                    elevation: 0
                    padding: [dp(14 * root.layout_scale)] * 4
                    adaptive_height: True

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(6 * root.layout_scale)
                        adaptive_height: True

                        MDLabel:
                            text: "Transfer instructions"
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            font_size: sp(13 * root.text_scale)
                            bold: True

                        MDLabel:
                            text: "Merchant number"
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11 * root.text_scale)
                            adaptive_height: True

                        MDLabel:
                            text: root.merchant_number
                            theme_text_color: "Custom"
                            text_color: GOLD
                            font_size: sp(16 * root.text_scale)
                            bold: True
                            adaptive_height: True

                        MDLabel:
                            text: "Status"
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11 * root.text_scale)
                            adaptive_height: True

                        MDLabel:
                            text: root.sale_status_display
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            font_size: sp(12.5 * root.text_scale)
                            adaptive_height: True

                        MDLabel:
                            text: root.transfer_instructions
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True
                            text_size: self.width, None

                        MDLabel:
                            text: root.flow_hint
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11 * root.text_scale)
                            adaptive_height: True
                            text_size: self.width, None

                MDLabel:
                    text: root.feedback_text
                    theme_text_color: "Custom"
                    text_color: root.feedback_color
                    adaptive_height: True

                Widget:
                    size_hint_y: None
                    height: dp(16 * root.layout_scale)
"""


class AirtimeCashScreen(ActionScreen):
    selected_network = StringProperty("")
    network_helper_text = StringProperty("We will auto-detect the network from the phone number.")
    payout_rate = NumericProperty(DEFAULT_PAYOUT_RATE)
    payout_estimate = StringProperty("GHS 0.00")
    fee_estimate = StringProperty("GHS 0.00")
    rate_hint = StringProperty("Rate: 80% payout (GHS 100 -> GHS 80)")
    merchant_number = StringProperty("Tap Generate to get a merchant number.")
    transfer_instructions = StringProperty(
        "Tap Generate Merchant Number, send airtime, then tap 'I Have Sent Airtime'."
    )
    flow_hint = StringProperty(
        "Flow: 1) Generate merchant number 2) Send airtime 3) We verify receipt 4) MoMo payout sent."
    )
    sale_id = StringProperty("")
    sale_status = StringProperty("")
    sale_status_display = StringProperty("Not submitted")

    def on_kv_post(self, _base_widget):
        super().on_kv_post(_base_widget)
        self._update_estimate()
        self._update_rate_hint()

    def _sync_network_input(self) -> None:
        field = self.ids.get("network_input")
        if field is not None:
            field.text = self.selected_network or ""

    def _parse_amount(self, raw: str | None = None) -> float:
        if raw is None:
            raw = self.ids.get("amount_input").text if self.ids.get("amount_input") else ""
        try:
            value = float(str(raw or "").replace(",", "").strip())
        except ValueError:
            return 0.0
        return value if value > 0 else 0.0

    def _update_estimate(self, raw: str | None = None) -> None:
        amount = self._parse_amount(raw)
        payout = amount * float(self.payout_rate or DEFAULT_PAYOUT_RATE)
        fee = max(amount - payout, 0.0)
        self.payout_estimate = f"GHS {payout:,.2f}"
        self.fee_estimate = f"GHS {fee:,.2f}"
        self._update_rate_hint()

    def _update_rate_hint(self) -> None:
        rate = float(self.payout_rate or DEFAULT_PAYOUT_RATE)
        sample_amount = 100.0
        sample_payout = sample_amount * rate
        self.rate_hint = f"Rate: {rate * 100:.0f}% payout (GHS {sample_amount:.0f} -> GHS {sample_payout:.0f})"

    def _set_sale_status(self, status: str | None) -> None:
        self.sale_status = str(status or "").strip()
        if self.sale_status:
            self.sale_status_display = self.sale_status.replace("_", " ").title()
        else:
            self.sale_status_display = "Not submitted"

    def on_amount_change(self, value: str) -> None:
        self._update_estimate(value)

    def on_phone_change(self, value: str) -> None:
        normalized = normalize_ghana_number(value)
        detected = detect_network(normalized)
        if detected and detected != "UNKNOWN":
            self.selected_network = detected
            self.network_helper_text = f"Detected {detected} from {normalized}."
            self._sync_network_input()
        else:
            self.network_helper_text = "Enter a valid Ghana number to auto-detect the network."

    def on_manual_network(self, value: str) -> None:
        raw = str(value or "").strip().upper()
        if not raw:
            return
        if "MTN" in raw:
            self.selected_network = "MTN"
        elif "TELECEL" in raw or "VODAFONE" in raw:
            self.selected_network = "TELECEL"
        elif "AIRTEL" in raw or "TIGO" in raw:
            self.selected_network = "AIRTELTIGO"
        else:
            self.selected_network = raw
        self.network_helper_text = f"Network set to {self.selected_network}."

    def is_network_selected(self, network: str) -> bool:
        return self.selected_network == network

    def select_network(self, network: str) -> None:
        self.selected_network = str(network or "").strip().upper()
        if self.selected_network:
            self.network_helper_text = f"{self.selected_network} selected."
        self._sync_network_input()

    def generate_merchant_number(self) -> None:
        phone = normalize_ghana_number(self.ids.get("phone_input").text if self.ids.get("phone_input") else "")
        amount = self._parse_amount()
        network = self.selected_network or detect_network(phone)

        if not phone or len(phone) != 10 or not phone.isdigit():
            self._set_feedback("Enter a valid 10-digit phone number to continue.", "error")
            return
        if not amount:
            self._set_feedback("Enter the airtime amount you want to sell.", "error")
            return
        if not network or network == "UNKNOWN":
            self._set_feedback("Select a valid network to continue.", "error")
            return

        self.selected_network = network
        self._sync_network_input()
        self._update_estimate(str(amount))
        self._set_feedback("Requesting merchant number...", "info")
        ok, payload = self._request(
            "POST",
            "/api/airtime/cash/quote",
            payload={"phone": phone, "network": network, "amount": amount, "currency": "GHS"},
        )

        if ok and isinstance(payload, dict):
            self.sale_id = str(payload.get("sale_id") or "")
            self._set_sale_status(payload.get("status"))
            self.merchant_number = payload.get("merchant_number") or MERCHANT_NUMBERS.get(
                network, MERCHANT_NUMBERS["DEFAULT"]
            )
            payout_rate = payload.get("payout_rate")
            if payout_rate is not None:
                try:
                    self.payout_rate = float(payout_rate)
                except Exception:
                    pass
            self._update_estimate(str(amount))
            self.transfer_instructions = payload.get("instructions") or (
                f"Send GHS {amount:,.2f} airtime from {phone} to {self.merchant_number}. "
                f"We will verify the transfer and pay out about {self.payout_estimate} to your MoMo."
            )
            self._set_feedback(
                "Merchant number generated. Transfer the airtime and tap 'I Have Sent Airtime'.",
                "success",
            )
            return

        detail = self._extract_detail(payload) or "Unable to generate a merchant number."
        self._set_feedback(detail, "error")

    def confirm_transfer(self) -> None:
        if not self.sale_id:
            self._set_feedback("Generate a merchant number first.", "warning")
            return

        self._set_feedback("Submitting transfer confirmation...", "info")
        ok, payload = self._request(
            "POST",
            "/api/airtime/cash/confirm",
            payload={"sale_id": self.sale_id},
        )
        if ok and isinstance(payload, dict):
            self._set_sale_status(payload.get("status"))
            status_text = self.sale_status_display or "Submitted"
            self._set_feedback(
                f"Transfer noted. Status: {status_text}. Verification is in progress.",
                "success",
            )
            return

        detail = self._extract_detail(payload) or "Unable to confirm the transfer."
        self._set_feedback(detail, "error")


Builder.load_string(KV)
