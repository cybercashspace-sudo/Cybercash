from kivy.lang import Builder
from kivy.properties import StringProperty

from core.screen_actions import ActionScreen

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
<PayBillsScreen>:
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
                        text: "Pay Bills"
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
                    text: "Settle utilities and invoices securely."
                    theme_text_color: "Custom"
                    text_color: TEXT_SUB
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
                        spacing: dp(8 * root.layout_scale)
                        adaptive_height: True

                        MDLabel:
                            text: "Biller name"
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            font_size: sp(13 * root.text_scale)

                        MDTextField:
                            id: biller_input
                            hint_text: "e.g. ECG, GWCL, DSTV"
                            mode: "outlined"

                        MDLabel:
                            text: "Account or meter number"
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            font_size: sp(13 * root.text_scale)

                        MDTextField:
                            id: account_input
                            hint_text: "Account or meter number"
                            mode: "outlined"

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
                            text: "Reference (optional)"
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            font_size: sp(13 * root.text_scale)

                        MDTextField:
                            id: reference_input
                            hint_text: "Reference or note"
                            mode: "outlined"

                        MDFillRoundFlatIconButton:
                            text: "Submit Bill Payment"
                            icon: "file-send-outline"
                            md_bg_color: GOLD_SOFT
                            text_color: BG
                            size_hint_y: None
                            height: dp(52 * root.layout_scale)
                            on_release: root.submit_bill_payment()

                        MDLabel:
                            text: root.bill_hint
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11 * root.text_scale)
                            adaptive_height: True

                MDLabel:
                    text: root.feedback_text
                    theme_text_color: "Custom"
                    text_color: root.feedback_color
                    adaptive_height: True

                Widget:
                    size_hint_y: None
                    height: dp(16 * root.layout_scale)
"""


class PayBillsScreen(ActionScreen):
    bill_hint = StringProperty("Bill payments are verified before final confirmation.")

    def submit_bill_payment(self) -> None:
        biller = str(self.ids.get("biller_input").text if self.ids.get("biller_input") else "").strip()
        account = str(self.ids.get("account_input").text if self.ids.get("account_input") else "").strip()
        raw_amount = str(self.ids.get("amount_input").text if self.ids.get("amount_input") else "").strip()

        try:
            amount = float(raw_amount.replace(",", "")) if raw_amount else 0.0
        except ValueError:
            amount = 0.0

        if not biller or not account:
            self._set_feedback("Enter the biller name and account number to continue.", "error")
            return
        if amount <= 0:
            self._set_feedback("Enter a valid amount to continue.", "error")
            return

        self._set_feedback("Bill payment request submitted. We will confirm once processed.", "success")


Builder.load_string(KV)
