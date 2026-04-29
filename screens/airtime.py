from kivy.lang import Builder
from kivy.properties import BooleanProperty, StringProperty

from core.screen_actions import ActionScreen
from utils.network import detect_network, normalize_ghana_number

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
<AirtimeScreen>:
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
                        text: "Buy Airtime"
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
                            text: "Phone number"
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            font_size: sp(13 * root.text_scale)

                        MDTextField:
                            id: phone_input
                            hint_text: "Phone number, e.g. 0241234567"
                            mode: "outlined"
                            on_text: root.on_phone_change(self.text)

                        MDLabel:
                            text: "We will auto-detect the network from the number."
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

                        MDLabel:
                            text: root.network_helper_text
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11 * root.text_scale)
                            adaptive_height: True

                        MDTextField:
                            id: network_input
                            hint_text: "Selected network (auto)"
                            mode: "outlined"
                            on_text: root.on_manual_network(self.text)

                        MDLabel:
                            text: "Amount"
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            font_size: sp(13 * root.text_scale)

                        MDTextField:
                            id: amount_input
                            hint_text: "Amount in GHS"
                            mode: "outlined"
                            input_filter: "float"

                        MDLabel:
                            text: "Enter the amount you want to top up."
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11 * root.text_scale)
                            adaptive_height: True

                        MDFillRoundFlatIconButton:
                            text: "Purchase Airtime"
                            icon: "cellphone"
                            md_bg_color: GOLD_SOFT
                            text_color: BG
                            size_hint_y: None
                            height: dp(52 * root.layout_scale)
                            on_release: root.purchase_airtime()

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


class AirtimeScreen(ActionScreen):
    selected_network = StringProperty("")
    network_helper_text = StringProperty("Select your network or type it below.")
    network_source_manual = BooleanProperty(False)

    def on_pre_enter(self):
        if not self.feedback_text:
            self._set_feedback("Enter phone number, select network, and amount to continue.", "info")
        if not self.network_helper_text:
            self.network_helper_text = "Select your network or type it below."
        if not self.selected_network:
            self.network_source_manual = False

    def on_phone_change(self, raw_value: str) -> None:
        detected = detect_network(str(raw_value or ""))
        detected_key = "TELECEL" if detected in {"TELECEL", "VODAFONE"} else str(detected or "").strip().upper()
        if detected_key and detected_key != "UNKNOWN":
            if not self.network_source_manual:
                self.select_network(detected_key, auto=True)
            elif not self.is_network_selected(detected_key):
                self.network_helper_text = f"Detected: {self._friendly_network_label(detected_key)}. Tap to switch."
            else:
                self.network_helper_text = f"Auto-detected: {self._friendly_network_label(detected_key)}"
        elif not self.selected_network:
            self.network_helper_text = "Select your network or type it below."

    def on_manual_network(self, raw_value: str) -> None:
        cleaned = self._normalize_network(raw_value)
        if cleaned in {"MTN", "VODAFONE", "AIRTELTIGO"}:
            self.selected_network = "TELECEL" if cleaned == "VODAFONE" else cleaned
            self.network_source_manual = True
            self.network_helper_text = f"Selected: {self._friendly_network_label(self.selected_network)}"

    def select_network(self, network: str, auto: bool = False) -> None:
        chosen = str(network or "").strip().upper()
        if chosen not in {"MTN", "TELECEL", "AIRTELTIGO"}:
            return
        self.selected_network = chosen
        self.network_source_manual = not auto
        self.ids.network_input.text = self._friendly_network_label(chosen)
        if auto:
            self.network_helper_text = f"Auto-detected: {self._friendly_network_label(chosen)}"
        else:
            self.network_helper_text = f"Selected: {self._friendly_network_label(chosen)}"

    def is_network_selected(self, network: str) -> bool:
        return str(self.selected_network or "").strip().upper() == str(network or "").strip().upper()

    @staticmethod
    def _friendly_network_label(network: str) -> str:
        key = str(network or "").strip().upper()
        if key in {"TELECEL", "VODAFONE"}:
            return "Telecel"
        if key == "AIRTELTIGO":
            return "AirtelTigo"
        if key == "MTN":
            return "MTN"
        return key.title()

    @staticmethod
    def _parse_amount(raw_amount: str) -> float:
        try:
            return float(str(raw_amount or "").strip())
        except Exception:
            return 0.0

    @staticmethod
    def _normalize_network(raw_value: str) -> str:
        text = str(raw_value or "").strip().upper()
        if text in {"VODAFONE", "TELECEL"}:
            return "VODAFONE"
        if text in {"AIRTELTIGO", "AIRTEL TIGO", "AT"}:
            return "AIRTELTIGO"
        if text == "MTN":
            return "MTN"
        return text

    def purchase_airtime(self):
        phone = normalize_ghana_number(self.ids.phone_input.text.strip())
        amount = self._parse_amount(self.ids.amount_input.text)
        network_raw = self.ids.network_input.text.strip() or self.selected_network
        inferred = detect_network(phone)
        network = self._normalize_network(network_raw or inferred)

        if not phone or len(phone) != 10:
            self._set_feedback("Please enter a valid phone number.", "error")
            self._show_popup("Invalid Number", "Use a valid 10-digit Ghana phone number.")
            return
        if amount <= 0:
            self._set_feedback("Please enter a valid airtime amount.", "error")
            self._show_popup("Invalid Amount", "Airtime amount must be greater than zero.")
            return
        if network not in {"MTN", "VODAFONE", "AIRTELTIGO"}:
            self._set_feedback("Please enter a valid network.", "error")
            self._show_popup("Invalid Network", "Use MTN, Telecel, or AirtelTigo.")
            return

        self._set_feedback("Submitting airtime purchase...", "info")
        ok, payload = self._request(
            "POST",
            "/api/airtime/purchase",
            payload={"network": network, "phone": phone, "amount": amount},
        )
        if ok and isinstance(payload, dict):
            tx_id = payload.get("id")
            msg = "Airtime purchased successfully."
            if tx_id:
                msg = f"Airtime purchased successfully. Transaction #{tx_id}."
            self._set_feedback(msg, "success")
            self._show_popup("Purchase Successful", msg)
            return

        detail = self._extract_detail(payload) or "Unable to complete airtime purchase."
        self._set_feedback(detail, "error")
        self._show_popup("Purchase Failed", detail)


Builder.load_string(KV)
