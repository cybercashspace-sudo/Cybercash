from kivy.lang import Builder
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.core.clipboard import Clipboard
from kivy.clock import Clock
from kivymd.app import MDApp
from core.screen_actions import ActionScreen
from core.popup_manager import show_message_dialog, show_confirm_dialog

KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp
#:import get_color_from_hex kivy.utils.get_color_from_hex

#:set BACKGROUND "#12110D"
#:set CARD_BLUE (0.07, 0.19, 0.42, 1)
#:set GOLD "#E7C96E"
#:set WHITE "#F8F8F8"
#:set GREEN "#A6D88F"
#:set ACTION_BG "#22221E"

<VirtualCardScreen>:
    name: "virtual_card"
    MDBoxLayout:
        orientation: "vertical"
        md_bg_color: get_color_from_hex(BACKGROUND)

        MDTopAppBar:
            title: "Virtual Card"
            anchor_title: "center"
            elevation: 0
            md_bg_color: get_color_from_hex(BACKGROUND)
            specific_text_color: get_color_from_hex(GOLD)
            left_action_items: [["arrow-left", lambda x: root.go_back()]]
            right_action_items: [["refresh", lambda x: root.refresh_data()]]

        ScrollView:
            do_scroll_x: False
            bar_width: 0

            MDBoxLayout:
                orientation: "vertical"
                adaptive_height: True
                padding: [dp(16 * root.layout_scale), dp(10 * root.layout_scale), dp(16 * root.layout_scale), dp(30 * root.layout_scale)]
                spacing: dp(20 * root.layout_scale)

                # 1. Virtual Visa Card (Hero)
                MDCard:
                    size_hint_y: None
                    height: dp(260 * root.layout_scale)
                    radius: [35]
                    elevation: 0
                    padding: dp(24 * root.layout_scale)

                    canvas.before:
                        Color:
                            rgba: CARD_BLUE
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [35]

                    FloatLayout:
                        MDLabel:
                            text: "VIRTUAL"
                            font_size: sp(24 * root.text_scale)
                            theme_text_color: "Custom"
                            text_color: get_color_from_hex(WHITE)
                            pos_hint: {"top": 1, "x": 0}
                            size_hint: None, None
                            size: self.texture_size

                        MDLabel:
                            text: "VISA"
                            bold: True
                            font_size: sp(34 * root.text_scale)
                            theme_text_color: "Custom"
                            text_color: get_color_from_hex(WHITE)
                            pos_hint: {"top": 1, "right": 1}
                            size_hint: None, None
                            size: self.texture_size

                        MDLabel:
                            id: card_number_label
                            text: root.card_number_display
                            font_size: sp(30 * root.text_scale)
                            halign: "center"
                            theme_text_color: "Custom"
                            text_color: get_color_from_hex(WHITE)
                            pos_hint: {"center_y": 0.55, "center_x": 0.5}

                        MDLabel:
                            text: "CARD HOLDER"
                            font_size: sp(12 * root.text_scale)
                            theme_text_color: "Custom"
                            text_color: [1, 1, 1, 0.7]
                            pos_hint: {"y": 0.12, "x": 0}
                            size_hint_y: None
                            height: dp(15)

                        MDLabel:
                            text: root.cardholder
                            font_size: sp(18 * root.text_scale)
                            bold: True
                            theme_text_color: "Custom"
                            text_color: get_color_from_hex(WHITE)
                            pos_hint: {"y": 0, "x": 0}
                            size_hint_y: None
                            height: dp(25)

                        MDLabel:
                            text: "EXPIRES"
                            font_size: sp(12 * root.text_scale)
                            theme_text_color: "Custom"
                            text_color: [1, 1, 1, 0.7]
                            pos_hint: {"y": 0.12, "x": 0.75}
                            size_hint_y: None
                            height: dp(15)

                        MDLabel:
                            text: root.expiry
                            font_size: sp(18 * root.text_scale)
                            bold: True
                            theme_text_color: "Custom"
                            text_color: get_color_from_hex(WHITE)
                            pos_hint: {"y": 0, "x": 0.75}
                            size_hint_y: None
                            height: dp(25)

                        MDLabel:
                            text: "CVV"
                            font_size: sp(12 * root.text_scale)
                            theme_text_color: "Custom"
                            text_color: [1, 1, 1, 0.7]
                            pos_hint: {"y": 0.12, "x": 0.45}
                            size_hint_y: None
                            height: dp(15)

                        MDLabel:
                            text: root.cvv
                            font_size: sp(18 * root.text_scale)
                            bold: True
                            theme_text_color: "Custom"
                            text_color: get_color_from_hex(WHITE)
                            pos_hint: {"y": 0, "x": 0.45}
                            size_hint_y: None
                            height: dp(25)

                # 2. Action Row
                MDGridLayout:
                    cols: 2
                    adaptive_height: True
                    spacing: dp(12 * root.layout_scale)

                    # Show/Hide Button
                    MDCard:
                        size_hint_y: None
                        height: dp(72 * root.layout_scale)
                        radius: [24]
                        md_bg_color: get_color_from_hex(ACTION_BG)
                        elevation: 0
                        on_release: root.toggle_details()
                        MDBoxLayout:
                            padding: dp(12)
                            spacing: dp(8)
                            MDIcon:
                                icon: "eye-outline" if not root.details_visible else "eye-off-outline"
                                theme_text_color: "Custom"
                                text_color: get_color_from_hex(GOLD)
                                pos_hint: {"center_y": .5}
                            MDLabel:
                                text: "Details" if not root.details_visible else "Hide"
                                theme_text_color: "Custom"
                                text_color: get_color_from_hex(WHITE)
                                font_size: sp(13 * root.text_scale)
                                valign: "center"

                    # Copy Button
                    MDCard:
                        size_hint_y: None
                        height: dp(72 * root.layout_scale)
                        radius: [24]
                        md_bg_color: get_color_from_hex(ACTION_BG)
                        elevation: 0
                        on_release: root.copy_card_number()
                        MDBoxLayout:
                            padding: dp(12)
                            spacing: dp(8)
                            MDIcon:
                                icon: "content-copy"
                                theme_text_color: "Custom"
                                text_color: get_color_from_hex(GOLD)
                                pos_hint: {"center_y": .5}
                            MDLabel:
                                text: "Copy"
                                theme_text_color: "Custom"
                                text_color: get_color_from_hex(WHITE)
                                font_size: sp(13 * root.text_scale)
                                valign: "center"

                    # Freeze Button
                    MDCard:
                        size_hint_y: None
                        height: dp(72 * root.layout_scale)
                        radius: [24]
                        md_bg_color: get_color_from_hex(ACTION_BG)
                        elevation: 0
                        on_release: root.toggle_freeze()
                        MDBoxLayout:
                            padding: dp(12)
                            spacing: dp(8)
                            MDIcon:
                                icon: "snowflake" if not root.is_frozen else "fire"
                                theme_text_color: "Custom"
                                text_color: get_color_from_hex(GOLD)
                                pos_hint: {"center_y": .5}
                            MDLabel:
                                text: "Freeze" if not root.is_frozen else "Unfreeze"
                                theme_text_color: "Custom"
                                text_color: get_color_from_hex(WHITE)
                                font_size: sp(13 * root.text_scale)
                                valign: "center"

                    # Replace Button
                    MDCard:
                        size_hint_y: None
                        height: dp(72 * root.layout_scale)
                        radius: [24]
                        md_bg_color: get_color_from_hex(ACTION_BG)
                        elevation: 0
                        on_release: root.replace_card_flow()
                        MDBoxLayout:
                            padding: dp(12)
                            spacing: dp(8)
                            MDIcon:
                                icon: "credit-card-refresh-outline"
                                theme_text_color: "Custom"
                                text_color: get_color_from_hex(GOLD)
                                pos_hint: {"center_y": .5}
                            MDLabel:
                                text: "Replace"
                                theme_text_color: "Custom"
                                text_color: get_color_from_hex(WHITE)
                                font_size: sp(13 * root.text_scale)
                                valign: "center"

                # 3. Load Card Panel
                MDCard:
                    radius: [32]
                    adaptive_height: True
                    md_bg_color: get_color_from_hex(ACTION_BG)
                    elevation: 0
                    padding: dp(24 * root.layout_scale)

                    MDBoxLayout:
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: dp(16 * root.layout_scale)

                        MDLabel:
                            text: "Load Card"
                            font_size: sp(20 * root.text_scale)
                            bold: True
                            theme_text_color: "Custom"
                            text_color: get_color_from_hex(GOLD)

                        MDBoxLayout:
                            adaptive_height: True
                            MDLabel:
                                text: "Wallet Balance:"
                                theme_text_color: "Custom"
                                text_color: get_color_from_hex(WHITE)
                            MDLabel:
                                text: root.wallet_balance_display
                                halign: "right"
                                bold: True
                                theme_text_color: "Custom"
                                text_color: get_color_from_hex(GOLD)

                        MDCard:
                            size_hint_y: None
                            height: dp(95 * root.layout_scale)
                            radius: [16]
                            md_bg_color: [1, 1, 1, 0.05]
                            elevation: 0
                            padding: [dp(16), 0]
                            
                            MDTextField:
                                id: load_amount
                                hint_text: "Amount to load (GHS)"
                                mode: "fill"
                                fill_color_normal: [0,0,0,0]
                                input_filter: "float"
                                theme_text_color: "Custom"
                                text_color_normal: get_color_from_hex(WHITE)
                                hint_text_color_normal: [1,1,1,0.5]
                                pos_hint: {"center_y": .5}

                        MDLabel:
                            text: "Card Loading Fee: GHS 1.50 (Standard rate)"
                            font_size: sp(12 * root.text_scale)
                            theme_text_color: "Custom"
                            text_color: [1, 1, 1, 0.6]

                        MDRaisedButton:
                            text: "Load Card"
                            size_hint_x: 1
                            height: dp(72 * root.layout_scale)
                            md_bg_color: get_color_from_hex(GOLD)
                            text_color: get_color_from_hex(BACKGROUND)
                            font_size: sp(18 * root.text_scale)
                            bold: True
                            disabled: root.processing
                            on_release: root.submit_load()

                # 4. Transaction History Panel
                MDCard:
                    radius: [32]
                    adaptive_height: True
                    md_bg_color: get_color_from_hex(ACTION_BG)
                    elevation: 0
                    padding: dp(24 * root.layout_scale)

                    MDBoxLayout:
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: dp(16 * root.layout_scale)

                        MDBoxLayout:
                            adaptive_height: True
                            MDLabel:
                                text: "Recent Transactions"
                                font_size: sp(20 * root.text_scale)
                                bold: True
                                theme_text_color: "Custom"
                                text_color: get_color_from_hex(GOLD)
                            
                            MDIconButton:
                                icon: "file-download-outline"
                                theme_text_color: "Custom"
                                text_color: get_color_from_hex(GOLD)
                                user_font_size: "24sp"
                                pos_hint: {"center_y": .5}
                                on_release: root.download_statement()

                        MDBoxLayout:
                            id: transaction_list
                            orientation: "vertical"
                            adaptive_height: True
                            spacing: dp(10 * root.layout_scale)

                MDLabel:
                    text: root.feedback_text
                    theme_text_color: "Custom"
                    text_color: root.feedback_color
                    adaptive_height: True
                    font_size: sp(12 * root.text_scale)

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
    card_number_display = StringProperty("••••  ••••  ••••  ••••")
    cardholder = StringProperty("Loading...")
    expiry = StringProperty("--/--")
    cvv = StringProperty("***")
    wallet_balance_display = StringProperty("GHS 0.00")
    details_visible = BooleanProperty(False)
    is_frozen = BooleanProperty(False)
    processing = BooleanProperty(False)
    
    _raw_number = ""
    _raw_cvv = ""
    _card_loaded = False
    _balance_val = 0.0

    def on_pre_enter(self):
        if not self._card_loaded:
            self.refresh_data()

    def refresh_data(self):
        self._set_feedback("Syncing card data...", "info")
        self.load_card_data()
        self.load_wallet()
        self.load_card_transactions()

    def load_card_data(self):
        ok, payload = self._request("GET", "/api/virtual-card")
        if ok and isinstance(payload, dict):
            self._raw_number = str(payload.get("card_number", ""))
            self._raw_cvv = str(payload.get("cvv", "***"))
            self.cardholder = str(payload.get("card_holder") or MDApp.get_running_app().pending_momo or "User")
            self.expiry = str(payload.get("expiry") or "12/27")
            self.is_frozen = payload.get("status") == "frozen"
            self._update_number_visibility()
            self._card_loaded = True
        else:
            self.cardholder = "No Active Card"
            self._set_feedback("Failed to load card details.", "error")

    def load_wallet(self):
        ok, payload = self._request("GET", "/wallet/me")
        if ok and isinstance(payload, dict):
            self._balance_val = float(payload.get("balance", 0.0))
            self.wallet_balance_display = f"GHS {self._balance_val:,.2f}"

    def load_card_transactions(self):
        # Fetching transactions specifically for the virtual card spend
        ok, payload = self._request("GET", "/api/virtual-card/transactions")
        if ok and isinstance(payload, list):
            self._render_transactions(payload)
        else:
            # Show fallback or empty state if no transactions exist
            self._render_transactions([])

    def _render_transactions(self, items):
        container = self.ids.transaction_list
        container.clear_widgets()
        
        if not items:
            container.add_widget(MDLabel(
                text="No recent transactions found.",
                theme_text_color="Secondary",
                halign="center",
                font_size=sp(14 * self.text_scale),
                adaptive_height=True,
                padding=[0, dp(20)]
            ))
            return

        for item in items[:10]:
            card = MDCard(
                adaptive_height=True,
                md_bg_color=[1, 1, 1, 0.03],
                radius=[16],
                padding=dp(16),
                elevation=0
            )
            row = MDBoxLayout(orientation="horizontal", spacing=dp(12))
            
            # Merchant and Info
            row.add_widget(MDLabel(
                text=str(item.get("merchant") or "Online Purchase"),
                theme_text_color="Custom",
                text_color=[1, 1, 1, 0.9],
                bold=True
            ))
            
            # Amount Spend
            row.add_widget(MDLabel(
                text=f"-${float(item.get('amount', 0.0)):,.2f}",
                halign="right",
                bold=True,
                theme_text_color="Custom",
                text_color=get_color_from_hex("#F8F8F8")
            ))
            card.add_widget(row)
            container.add_widget(card)

    def _update_number_visibility(self):
        if self.details_visible:
            self.card_number_display = self._raw_number
        else:
            last4 = self._raw_number[-4:] if len(self._raw_number) >= 4 else "0000"
            self.card_number_display = f"••••  ••••  ••••  {last4}"

    def toggle_details(self):
        self.details_visible = not self.details_visible
        self._update_number_visibility()
        
        if self.details_visible:
            # Logic to trigger the reveal popup as requested
            self.show_cvv_popup()

    def show_cvv_popup(self):
        if not self._raw_cvv:
            return
            
        show_message_dialog(
            self,
            title="Security Reveal",
            message=f"Your Card CVV is: [b]{self._raw_cvv}[/b]\\n\\nThis code expires from this view once you hide details.",
            close_label="I Understand"
        )

    def copy_card_number(self):
        if self._raw_number:
            Clipboard.copy(self._raw_number)
            self._set_feedback("Card number copied to clipboard", "success")
        else:
            self._set_feedback("No card number available to copy", "warning")

    def download_statement(self):
        self._set_feedback("Fetching statement URL...", "info")
        ok, payload = self._request("GET", "/api/virtual-card/statement")
        if ok and isinstance(payload, dict) and payload.get("url"):
            import webbrowser
            webbrowser.open(payload["url"])
            self._set_feedback("Statement download opened in browser", "success")
        else:
            self._set_feedback("Statement service is currently unavailable.", "warning")

    def replace_card_flow(self):
        show_confirm_dialog(
            self,
            title="Replace Virtual Card?",
            message="Your current card will be permanently deleted and a new one will be issued. Any remaining balance will be transferred automatically.",
            confirm_label="Replace Card",
            on_confirm=self._perform_replace
        )

    def _perform_replace(self):
        self._set_feedback("Processing card replacement...", "info")
        ok, payload = self._request("POST", "/api/virtual-card/replace")
        if ok:
            self._set_feedback("Card replaced successfully", "success")
            self.refresh_data()
        else:
            detail = self._extract_detail(payload) or "Failed to replace card"
            self._set_feedback(detail, "error")

    def toggle_freeze(self):
        new_state = not self.is_frozen
        status_str = "frozen" if new_state else "active"
        self._set_feedback(f"Updating card to {status_str}...", "info")
        
        ok, payload = self._request("POST", "/api/virtual-card/status", payload={"status": status_str})
        if ok:
            self.is_frozen = new_state
            self._set_feedback(f"Card is now {'Frozen' if self.is_frozen else 'Active'}", "success")
        else:
            self._set_feedback("Failed to update card status", "error")

    def submit_load(self):
        if self.processing:
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
            
        if amount > self._balance_val:
            self._set_feedback("Insufficient wallet balance", "error")
            return

        self.processing = True
        self._set_feedback("Processing card load...", "info")
        
        def _worker():
            ok, payload = self._request("POST", "/api/virtual-card/load", payload={"amount": amount})
            Clock.schedule_once(lambda dt: self._on_load_complete(ok, payload))
            
        import threading
        threading.Thread(target=_worker, daemon=True).start()

    def _on_load_complete(self, ok, payload):
        self.processing = False
        if ok:
            self._set_feedback("Card loaded successfully!", "success")
            self.ids.load_amount.text = ""
            self.refresh_data()
            show_message_dialog(self, title="Success", message="Your virtual card has been credited.")
        else:
            detail = self._extract_detail(payload) or "Failed to load card"
            self._set_feedback(detail, "error")

Builder.load_string(KV)