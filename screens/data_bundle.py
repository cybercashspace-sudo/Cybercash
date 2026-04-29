from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.properties import BooleanProperty, ColorProperty, NumericProperty, StringProperty
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel

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
<DataBundleScreen>:
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
                        text: root.screen_title
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
                    text: root.screen_subtitle
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
                            text: "Bundle code"
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            font_size: sp(13 * root.text_scale)

                        MDTextField:
                            id: bundle_input
                            hint_text: "Bundle code, e.g. 1GB"
                            mode: "outlined"

                        MDLabel:
                            text: root.bundle_helper_text
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11 * root.text_scale)
                            adaptive_height: True

                        MDBoxLayout:
                            adaptive_height: True

                            MDLabel:
                                text: "Bundle catalog"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_size: sp(14 * root.text_scale)
                                bold: True

                            MDTextButton:
                                text: "Refresh Catalog"
                                theme_text_color: "Custom"
                                text_color: GOLD
                                on_release: root.load_catalog()

                        MDGridLayout:
                            id: catalog_grid
                            cols: 1 if root.compact_mode else 2
                            spacing: dp(10 * root.layout_scale)
                            adaptive_height: True
                            size_hint_y: None
                            height: self.minimum_height

                        MDLabel:
                            text: root.catalog_hint
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            adaptive_height: True

                        MDFillRoundFlatIconButton:
                            text: root.action_button_text
                            icon: "wifi"
                            md_bg_color: GOLD_SOFT
                            text_color: BG
                            size_hint_y: None
                            height: dp(52 * root.layout_scale)
                            on_release: root.purchase_bundle()

                        MDLabel:
                            text: root.order_status_text
                            theme_text_color: "Custom"
                            text_color: root.order_status_color
                            font_size: sp(11 * root.text_scale)
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

CATALOG_CARD_BG = [0.10, 0.12, 0.16, 0.96]
CATALOG_CARD_LINE = [0.24, 0.30, 0.36, 0.45]
CATALOG_PRICE = [0.94, 0.79, 0.46, 1]
CATALOG_SUBTEXT = [0.72, 0.75, 0.78, 1]
STATIC_BUNDLE_CATALOG = {
    "MTN": [
        {"bundle_code": "1GB", "data": "1 GB", "price": 5.0},
        {"bundle_code": "2GB", "data": "2 GB", "price": 9.50},
        {"bundle_code": "5GB", "data": "5 GB", "price": 23.0},
        {"bundle_code": "10GB", "data": "10 GB", "price": 45.0},
        {"bundle_code": "25GB", "data": "25 GB", "price": 111.0},
        {"bundle_code": "50GB", "data": "50 GB", "price": 198.0},
    ],
    "TELECEL": [
        {"bundle_code": "10GB", "data": "10 GB", "price": 42.0},
        {"bundle_code": "25GB", "data": "25 GB", "price": 98.0},
        {"bundle_code": "50GB", "data": "50 GB", "price": 185.0},
        {"bundle_code": "100GB", "data": "100 GB", "price": 368.0},
    ],
    "AIRTELTIGO": [
        {"bundle_code": "2GB", "data": "2 GB", "price": 8.30},
        {"bundle_code": "5GB", "data": "5 GB", "price": 21.0},
        {"bundle_code": "10GB", "data": "10 GB", "price": 40.70},
        {"bundle_code": "30GB", "data": "30 GB", "price": 76.0},
        {"bundle_code": "50GB", "data": "50 GB", "price": 97.0},
        {"bundle_code": "100GB", "data": "100 GB", "price": 183.0},
    ],
}


class DataBundleScreen(ActionScreen):
    screen_title = StringProperty("Buy Data Bundle")
    screen_subtitle = StringProperty("Browse live prices, compare bundles, and complete a purchase in one flow.")
    action_button_text = StringProperty("Purchase Bundle")
    catalog_hint = StringProperty("Catalog auto-loads when a network is selected.")
    bundle_helper_text = StringProperty("Choose a bundle from the catalog or type a code.")
    selected_network = StringProperty("")
    network_helper_text = StringProperty("Select your network or type it below.")
    catalog_provider = StringProperty("")
    purchase_path = StringProperty("/api/bundles/purchase")
    network_source_manual = BooleanProperty(False)
    show_agent_pricing = BooleanProperty(False)
    agent_discount_ghs = NumericProperty(0.50)
    order_status_text = StringProperty("")
    order_status_color = ColorProperty([0.72, 0.74, 0.80, 1])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._catalog_items: list[dict] = []
        self._selected_bundle_id: int | None = None
        self._selected_bundle_price: float = 0.0
        self._suspend_network_sync = False

    @staticmethod
    def _friendly_order_status(raw_status: str, fallback: str = "") -> str:
        status = str(raw_status or "").strip().lower()
        if not status:
            return str(fallback or "").strip().title()
        if status in {"pending", "processing", "queued"}:
            return "Pending"
        if status in {"ordered", "order", "submitted", "received"}:
            return "Ordered"
        if status in {"completed", "complete", "successful", "success", "ok", "done"}:
            return "Complete"
        if status in {"cancelled", "canceled", "failed", "rejected", "abandoned", "error"}:
            return "Cancelled"
        return status.replace("_", " ").title()

    def _set_order_status(self, raw_status: str = "", fallback: str = "") -> None:
        label = self._friendly_order_status(raw_status, fallback)
        colors = {
            "Ordered": [0.93, 0.77, 0.39, 1],
            "Pending": [0.94, 0.79, 0.46, 1],
            "Complete": [0.55, 0.84, 0.66, 1],
            "Cancelled": [0.96, 0.47, 0.42, 1],
            "": [0.72, 0.74, 0.80, 1],
        }
        self.order_status_text = f"Order status: {label}" if label else ""
        self.order_status_color = colors.get(label, colors[""])

    def _clear_form_inputs(self) -> None:
        phone_input = self.ids.get("phone_input")
        if phone_input is not None:
            phone_input.text = ""
        bundle_input = self.ids.get("bundle_input")
        if bundle_input is not None:
            bundle_input.text = ""
        network_input = self.ids.get("network_input")
        if network_input is not None:
            self._suspend_network_sync = True
            try:
                network_input.text = ""
            finally:
                self._suspend_network_sync = False

    def configure_user_mode(self) -> None:
        self.show_agent_pricing = False
        self.purchase_path = "/api/bundles/purchase"
        self.catalog_provider = ""
        self.screen_title = "Buy Data Bundle"
        self.screen_subtitle = "Browse live prices, compare bundles, and complete a purchase in one flow."
        self.action_button_text = "Purchase Bundle"
        self.catalog_hint = "Catalog auto-loads when a network is selected."
        self.bundle_helper_text = "Choose a bundle from the catalog or type a code."
        self.network_helper_text = "Select your network or type it below."
        self.selected_network = ""
        self.network_source_manual = False
        self._catalog_items = []
        self._selected_bundle_id = None
        self._selected_bundle_price = 0.0
        self._clear_form_inputs()
        self.network_helper_text = "Select your network or type it below."
        self._render_catalog([])
        self._set_order_status("")
        self._set_feedback("Enter phone number, select network, and choose a bundle to continue.", "info")

    def configure_agent_mode(self) -> None:
        self.show_agent_pricing = True
        self.purchase_path = "/agent/data"
        self.catalog_provider = "idata"
        self.screen_title = "Sell Data Bundle"
        self.screen_subtitle = "Live iData bundles with a GHS 0.50 agent discount shown on every card."
        self.action_button_text = "Sell Bundle"
        self.catalog_hint = "Tap Refresh Catalog to load live iData bundles."
        self.bundle_helper_text = "Select a live iData bundle to see the agent price."
        self.network_helper_text = "Select a network to load live iData bundles."
        self.selected_network = ""
        self.network_source_manual = False
        self._catalog_items = []
        self._selected_bundle_id = None
        self._selected_bundle_price = 0.0
        self._clear_form_inputs()
        self.network_helper_text = "Select a network to load live iData bundles."
        self._render_catalog([])
        self._set_order_status("")
        self._set_feedback(
            "Select a network to load live iData bundles. Every card shows the GHS 0.50 agent discount.",
            "info",
        )

    def on_pre_enter(self):
        previous_screen = str(getattr(self.manager, "previous_screen", "") or "").strip().lower() if self.manager else ""
        if previous_screen == "agent":
            self.configure_agent_mode()
        else:
            self.configure_user_mode()

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

    def on_phone_change(self, raw_value: str) -> None:
        if self._suspend_network_sync:
            return
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
        if self._suspend_network_sync:
            return
        cleaned = self._normalize_network(raw_value)
        if cleaned in {"MTN", "VODAFONE", "AIRTELTIGO"}:
            self.selected_network = cleaned
            self.network_source_manual = True
            self.network_helper_text = f"Selected: {self._friendly_network_label(self.selected_network)}"
            self._selected_bundle_id = None
            self._selected_bundle_price = 0.0
            bundle_input = self.ids.get("bundle_input")
            if bundle_input is not None:
                bundle_input.text = ""
            if self.show_agent_pricing:
                self.catalog_hint = "Loading live iData bundles..."
                self.load_catalog()
            else:
                self._auto_load_catalog(self.selected_network)
        elif not self.selected_network:
            self.network_helper_text = "Select your network or type it below."

    def select_network(self, network: str, auto: bool = False) -> None:
        chosen = str(network or "").strip().upper()
        if chosen not in {"MTN", "TELECEL", "AIRTELTIGO"}:
            return
        self.selected_network = chosen
        self.network_source_manual = not auto
        self._selected_bundle_id = None
        self._selected_bundle_price = 0.0
        bundle_input = self.ids.get("bundle_input")
        if bundle_input is not None:
            bundle_input.text = ""
        network_input = self.ids.get("network_input")
        if network_input is not None:
            self._suspend_network_sync = True
            try:
                network_input.text = self._friendly_network_label(chosen)
            finally:
                self._suspend_network_sync = False
        if auto:
            self.network_helper_text = f"Auto-detected: {self._friendly_network_label(chosen)}"
        else:
            self.network_helper_text = f"Selected: {self._friendly_network_label(chosen)}"
        if self.show_agent_pricing:
            self.catalog_hint = "Loading live iData bundles..."
            self.load_catalog()
        else:
            self._auto_load_catalog(chosen)

    def is_network_selected(self, network: str) -> bool:
        return str(self.selected_network or "").strip().upper() == str(network or "").strip().upper()

    def _resolve_network(self, phone: str) -> str:
        network_input = self.ids.get("network_input")
        raw_network = network_input.text.strip() if network_input is not None else ""
        preferred = self.selected_network or raw_network
        inferred = detect_network(phone)
        return self._normalize_network(preferred or inferred)

    @staticmethod
    def _catalog_key(network: str) -> str:
        key = str(network or "").strip().upper()
        if key in {"VODAFONE", "TELECEL"}:
            return "TELECEL"
        if key == "AIRTELTIGO":
            return "AIRTELTIGO"
        if key == "MTN":
            return "MTN"
        return key

    def _auto_load_catalog(self, network: str) -> None:
        catalog_key = self._catalog_key(network)
        if self.show_agent_pricing:
            self._catalog_items = []
            self._render_catalog([])
            self.catalog_hint = "Tap Refresh Catalog to load live iData bundles."
            self.bundle_helper_text = "Select a live iData bundle to see the agent price."
            return
        static_payload = STATIC_BUNDLE_CATALOG.get(catalog_key, [])
        self._catalog_items = list(static_payload)
        self._render_catalog(static_payload)
        if static_payload:
            display_name = "Telecel" if catalog_key == "TELECEL" else catalog_key
            self.catalog_hint = f"{display_name} sample bundles loaded. Tap Refresh Catalog for live bundles."
            self.bundle_helper_text = "Tap a bundle card to auto-fill the code."
            bundle_input = self.ids.get("bundle_input")
            if static_payload and bundle_input is not None and not bundle_input.text.strip():
                bundle_input.text = static_payload[0].get("bundle_code", "")
        else:
            self.catalog_hint = "No bundles found for the selected network."

    @staticmethod
    def _extract_bundle_code(item: dict) -> str:
        return str(
            item.get("bundle_code")
            or item.get("code")
            or item.get("bundle")
            or item.get("bundle_id")
            or ""
        ).strip()

    @staticmethod
    def _extract_bundle_name(item: dict) -> str:
        return str(
            item.get("name")
            or item.get("bundle_name")
            or item.get("title")
            or ""
        ).strip()

    @staticmethod
    def _extract_price(item: dict) -> float | None:
        for key in ("price", "amount", "cost", "value"):
            if key in item:
                try:
                    return float(item.get(key) or 0.0)
                except Exception:
                    return None
        return None

    @staticmethod
    def _extract_meta(item: dict, keys: tuple[str, ...]) -> str:
        for key in keys:
            value = item.get(key)
            if value:
                return str(value).strip()
        return ""

    @staticmethod
    def _extract_bundle_id(item: dict) -> int | None:
        for key in ("id", "bundle_catalog_id", "catalog_id", "bundle_id"):
            if key in item and item.get(key) is not None:
                try:
                    return int(str(item.get(key)).strip())
                except Exception:
                    continue
        return None

    @staticmethod
    def _extract_status_label(*sources: dict) -> str:
        for source in sources:
            if not isinstance(source, dict):
                continue
            label = str(source.get("status_label") or "").strip()
            if label:
                return label
        return ""

    def _resolve_selected_catalog_item(self, bundle_code: str) -> dict:
        normalized_code = str(bundle_code or "").strip().upper()
        for item in self._catalog_items:
            if not isinstance(item, dict):
                continue
            if self._extract_bundle_code(item).upper() == normalized_code:
                return item
        return {}

    def _build_catalog_card(self, item: dict) -> MDCard:
        layout_scale = float(self.layout_scale or 1.0)
        text_scale = float(self.text_scale or 1.0)
        code = self._extract_bundle_code(item)
        name = self._extract_bundle_name(item)
        title = name or code or "Bundle"
        data_label = self._extract_meta(item, ("data", "size", "bundle_size", "volume"))
        validity = self._extract_meta(item, ("validity", "duration", "expiry", "period"))
        provider_label = self._extract_meta(item, ("provider",))
        price_value = self._extract_price(item)
        has_price = isinstance(price_value, float)
        user_price = round(float(price_value or 0.0), 2) if has_price else 0.0
        agent_discount = round(float(self.agent_discount_ghs or 0.0), 2)
        agent_price = round(max(user_price - agent_discount, 0.0), 2) if has_price else 0.0

        detail_parts = [part for part in (data_label, validity) if part]
        if self.show_agent_pricing and provider_label:
            detail_parts.insert(0, "iData live" if provider_label.lower() == "idata" else provider_label.title())
        detail_text = " | ".join(detail_parts) if detail_parts else "Data bundle"

        card = MDCard(
            size_hint_y=None,
            height=dp(112 * layout_scale if self.show_agent_pricing else 96 * layout_scale),
            radius=[dp(16 * layout_scale)],
            md_bg_color=CATALOG_CARD_BG,
            line_color=CATALOG_CARD_LINE,
            padding=[dp(12 * layout_scale), dp(10 * layout_scale), dp(12 * layout_scale), dp(10 * layout_scale)],
            elevation=0,
            on_release=lambda *_args, bundle=item: self._select_bundle(bundle),
        )

        body = MDBoxLayout(orientation="vertical", spacing=dp(4 * layout_scale))
        body.add_widget(
            MDLabel(
                text=title,
                theme_text_color="Custom",
                text_color=[0.94, 0.95, 0.97, 1],
                font_size=sp(14 * text_scale),
                bold=True,
                shorten=True,
                shorten_from="right",
            )
        )
        body.add_widget(
            MDLabel(
                text=detail_text,
                theme_text_color="Custom",
                text_color=CATALOG_SUBTEXT,
                font_size=sp(11 * text_scale),
                shorten=True,
                shorten_from="right",
            )
        )
        if has_price and self.show_agent_pricing:
            body.add_widget(
                MDLabel(
                    text=f"User price: GHS {user_price:,.2f}",
                    theme_text_color="Custom",
                    text_color=CATALOG_SUBTEXT,
                    font_size=sp(11.5 * text_scale),
                )
            )
            body.add_widget(
                MDLabel(
                    text=f"Agent price: GHS {agent_price:,.2f}  |  Save GHS {agent_discount:,.2f}",
                    theme_text_color="Custom",
                    text_color=CATALOG_PRICE,
                    font_size=sp(12.5 * text_scale),
                    bold=True,
                )
            )
        else:
            body.add_widget(
                MDLabel(
                    text=f"GHS {user_price:,.2f}" if has_price else "Tap to select",
                    theme_text_color="Custom",
                    text_color=CATALOG_PRICE if has_price else CATALOG_SUBTEXT,
                    font_size=sp(12.5 * text_scale),
                    bold=True,
                )
            )
        card.add_widget(body)
        return card

    def _render_catalog(self, items: list[dict]) -> None:
        container = self.ids.get("catalog_grid")
        if not container:
            return
        container.clear_widgets()

        if not items:
            empty = MDCard(
                size_hint_y=None,
                height=dp(84 * float(self.layout_scale or 1.0)),
                radius=[dp(16 * float(self.layout_scale or 1.0))],
                md_bg_color=CATALOG_CARD_BG,
                line_color=CATALOG_CARD_LINE,
                padding=[dp(12 * float(self.layout_scale or 1.0))] * 4,
                elevation=0,
            )
            empty.add_widget(
                MDLabel(
                    text=(
                        "Tap Refresh Catalog to load live iData bundles."
                        if self.show_agent_pricing
                        else "Load the catalog to see bundle packages and prices."
                    ),
                    theme_text_color="Custom",
                    text_color=CATALOG_SUBTEXT,
                    halign="center",
                    valign="middle",
                )
            )
            container.add_widget(empty)
            return

        for item in items:
            if isinstance(item, dict):
                container.add_widget(self._build_catalog_card(item))

    def _select_bundle(self, bundle_value) -> None:
        selected_item = bundle_value if isinstance(bundle_value, dict) else self._resolve_selected_catalog_item(str(bundle_value or ""))
        code = self._extract_bundle_code(selected_item) if isinstance(selected_item, dict) and selected_item else str(bundle_value or "").strip()
        if not code:
            return
        bundle_input = self.ids.get("bundle_input")
        if bundle_input is not None:
            bundle_input.text = code
        bundle_id = self._extract_bundle_id(selected_item) if isinstance(selected_item, dict) and selected_item else None
        price_value = self._extract_price(selected_item) if isinstance(selected_item, dict) and selected_item else None
        if bundle_id is not None:
            self._selected_bundle_id = bundle_id
        if isinstance(price_value, float):
            self._selected_bundle_price = price_value

        if self.show_agent_pricing and isinstance(price_value, float):
            agent_discount = round(float(self.agent_discount_ghs or 0.0), 2)
            agent_price = round(max(float(price_value or 0.0) - agent_discount, 0.0), 2)
            self.bundle_helper_text = (
                f"Selected bundle: {code} | User price GHS {price_value:,.2f} | Agent price GHS {agent_price:,.2f}"
            )
            self._set_feedback(
                f"Selected {code}. Agent price GHS {agent_price:,.2f} after the GHS {agent_discount:.2f} discount.",
                "info",
            )
        else:
            self.bundle_helper_text = f"Selected bundle: {code}"
            self._set_feedback(f"Selected {code}. Tap Purchase Bundle to continue.", "info")

    def load_catalog(self):
        phone_input = self.ids.get("phone_input")
        bundle_input = self.ids.get("bundle_input")
        phone = normalize_ghana_number(phone_input.text.strip() if phone_input is not None else "")
        network = self._resolve_network(phone)
        if network not in {"MTN", "VODAFONE", "AIRTELTIGO"}:
            self._set_feedback("Enter a valid network first.", "error")
            self._show_popup("Invalid Network", "Use MTN, Telecel, or AirtelTigo.")
            return

        self._set_feedback("Loading live iData bundles..." if self.show_agent_pricing else "Loading bundle catalog...", "info")
        catalog_key = self._catalog_key(network)
        params = {"network": network}
        if self.catalog_provider:
            params["provider"] = self.catalog_provider
        ok, payload = self._request("GET", "/api/bundles/catalog", params=params)
        if ok and isinstance(payload, list):
            self._catalog_items = payload
            self._render_catalog(payload)
            if not payload:
                if self.show_agent_pricing:
                    self.catalog_hint = f"No live iData bundles found for {self._friendly_network_label(network)}."
                    self.bundle_helper_text = "Choose another network or refresh again."
                else:
                    self.catalog_hint = "No active bundles found for the selected network."
                    self.bundle_helper_text = "Ask support/admin to enable bundles, then tap Refresh Catalog again."
                self._set_feedback(self.catalog_hint, "warning")
                return
            codes = [str(item.get("bundle_code", "")).strip() for item in payload if isinstance(item, dict)]
            codes = [code for code in codes if code]
            if self.show_agent_pricing:
                self.catalog_hint = "Tap a live iData bundle to auto-fill the code."
                self.bundle_helper_text = "Tap a bundle card to compare user and agent prices."
            else:
                self.catalog_hint = "Tap a bundle to auto-fill the code."
                self.bundle_helper_text = "Tap a bundle card to auto-fill the code."
            if codes and bundle_input is not None and not bundle_input.text.strip():
                bundle_input.text = codes[0]
            self._set_feedback("Live iData bundle catalog loaded." if self.show_agent_pricing else "Bundle catalog loaded.", "success")
            return

        if self.show_agent_pricing:
            detail = self._extract_detail(payload) or "Unable to load live iData bundles."
            self._set_feedback(detail, "error")
            self._show_popup("Catalog Error", detail)
            return

        static_payload = STATIC_BUNDLE_CATALOG.get(catalog_key, [])
        if static_payload:
            self._catalog_items = static_payload
            self._render_catalog(static_payload)
            display_name = "Telecel" if catalog_key == "TELECEL" else catalog_key
            self.catalog_hint = f"{display_name} offline bundles loaded. Tap a bundle to auto-fill."
            self.bundle_helper_text = "Tap a bundle card to auto-fill the code."
            if static_payload and bundle_input is not None and not bundle_input.text.strip():
                bundle_input.text = static_payload[0].get("bundle_code", "")
            fallback_note = self._extract_detail(payload)
            if fallback_note:
                self._set_feedback(f"{fallback_note} (showing offline catalog)", "warning")
            else:
                self._set_feedback("Offline bundle catalog loaded.", "warning")
            return

        detail = self._extract_detail(payload) or "Unable to load bundle catalog."
        self._set_feedback(detail, "error")
        self._show_popup("Catalog Error", detail)

    def purchase_bundle(self):
        phone_input = self.ids.get("phone_input")
        bundle_input = self.ids.get("bundle_input")
        phone = normalize_ghana_number(phone_input.text.strip() if phone_input is not None else "")
        network = self._resolve_network(phone)
        bundle_code = str(bundle_input.text if bundle_input is not None else "").strip().upper()

        if not phone or len(phone) != 10:
            self._set_feedback("Enter a valid phone number.", "error")
            self._set_order_status("cancelled")
            self._show_popup("Invalid Number", "Use a valid 10-digit Ghana phone number.")
            return
        if network not in {"MTN", "VODAFONE", "AIRTELTIGO"}:
            self._set_feedback("Enter a valid network.", "error")
            self._set_order_status("cancelled")
            self._show_popup("Invalid Network", "Use MTN, Telecel, or AirtelTigo.")
            return
        if self.show_agent_pricing:
            selected_item = self._resolve_selected_catalog_item(bundle_code)
            bundle_id = self._selected_bundle_id or self._extract_bundle_id(selected_item)
            if bundle_id is None:
                detail = "Select a live iData bundle from the catalog first."
                self._set_feedback(detail, "error")
                self._set_order_status("cancelled")
                self._show_popup("Missing Bundle", detail)
                return

            price_value = self._extract_price(selected_item) if selected_item else None
            if price_value is None:
                price_value = float(self._selected_bundle_price or 0.0)
            if price_value <= 0:
                detail = "This live bundle does not have a valid price yet."
                self._set_feedback(detail, "error")
                self._set_order_status("cancelled")
                self._show_popup("Missing Price", detail)
                return

            agent_discount = round(float(self.agent_discount_ghs or 0.0), 2)
            agent_price = round(max(float(price_value) - agent_discount, 0.0), 2)
            if agent_price <= 0:
                detail = "This bundle price is too low to apply the agent discount."
                self._set_feedback(detail, "error")
                self._set_order_status("cancelled")
                self._show_popup("Invalid Price", detail)
                return

            self._set_feedback("Submitting live iData bundle...", "info")
            self._set_order_status("ordered")
            ok, payload = self._request(
                "POST",
                self.purchase_path,
                payload={"network": network, "phone": phone, "bundle_id": int(bundle_id)},
            )
            if ok and isinstance(payload, dict):
                order = payload.get("order") if isinstance(payload.get("order"), dict) else {}
                provider_response = payload.get("provider_response") if isinstance(payload.get("provider_response"), dict) else {}
                charged_amount = float(order.get("amount") or agent_price)
                user_price = float(price_value)
                saved_amount = max(user_price - charged_amount, 0.0)
                order_status_raw = ""
                if isinstance(provider_response, dict):
                    order_status_raw = str(provider_response.get("status") or "").strip()
                if not order_status_raw and isinstance(order, dict):
                    order_status_raw = str(order.get("status") or "").strip()
                status_label = self._extract_status_label(order, provider_response) or self._friendly_order_status(
                    order_status_raw,
                    fallback="Complete",
                )
                self._set_order_status(status_label or order_status_raw, fallback="Complete")
                msg = (
                    f"{status_label}. Live iData bundle sold successfully. User price GHS {user_price:,.2f}; "
                    f"agent price GHS {charged_amount:,.2f}; save GHS {saved_amount:,.2f}."
                )
                self._set_feedback(msg, "success")
                self._show_popup("Sale Successful", msg)
                return

            detail = self._extract_detail(payload) or "Unable to complete live iData bundle sale."
            detail_lc = detail.lower()
            if "bundle not found" in detail_lc:
                detail = "That live bundle is no longer available. Refresh the catalog and choose another one."
            elif "idata provider is not configured" in detail_lc:
                detail = "Live iData bundles are temporarily unavailable. Please try again shortly."
            elif "missing idata package id" in detail_lc:
                detail = "This bundle is not ready yet. Tap Refresh Catalog and choose another live bundle."
            self._set_order_status("cancelled")
            self._set_feedback(detail, "error")
            self._show_popup("Sale Failed", detail)
            return

        if not bundle_code:
            self._set_feedback("Enter a bundle code.", "error")
            self._set_order_status("cancelled")
            self._show_popup("Missing Bundle Code", "Please select or type a valid bundle code.")
            return

        self._set_feedback("Submitting bundle purchase...", "info")
        self._set_order_status("ordered")
        ok, payload = self._request(
            "POST",
            self.purchase_path,
            payload={"network": network, "bundle_code": bundle_code, "phone": phone},
        )
        if ok and isinstance(payload, dict):
            tx_id = payload.get("id")
            order_status_raw = ""
            order_row = payload.get("order") if isinstance(payload.get("order"), dict) else {}
            if isinstance(order_row, dict):
                order_status_raw = str(order_row.get("status") or "").strip()
            status_label = self._extract_status_label(order_row, payload.get("provider_response")) or self._friendly_order_status(
                order_status_raw,
                fallback="Complete",
            )
            self._set_order_status(status_label or order_status_raw, fallback="Complete")
            msg = "Data bundle purchased successfully."
            if tx_id:
                msg = f"{status_label}. Data bundle purchased successfully. Transaction #{tx_id}."
            else:
                msg = f"{status_label}. Data bundle purchased successfully."
            self._set_feedback(msg, "success")
            self._show_popup("Purchase Successful", msg)
            return

        detail = self._extract_detail(payload) or "Unable to complete bundle purchase."
        detail_lc = detail.lower()
        if "bundle not found" in detail_lc:
            detail = (
                "Bundle code not found. Tap Refresh Catalog and select a bundle from the live list, "
                "or contact support if the bundle is missing."
            )
        elif "idata provider is not configured" in detail_lc:
            detail = "Data bundle service is temporarily unavailable. Please try again later."
        elif "missing idata package id" in detail_lc:
            detail = "This bundle is temporarily unavailable. Tap Refresh Catalog or choose another bundle."
        self._set_order_status("cancelled")
        self._set_feedback(detail, "error")
        self._show_popup("Purchase Failed", detail)


Builder.load_string(KV)
