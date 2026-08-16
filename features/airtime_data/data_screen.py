from pathlib import Path
from threading import Thread

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import BooleanProperty
from kivy.properties import ObjectProperty
from kivy.properties import StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from components.app_snackbar import show_app_snackbar

from features.airtime_data.data_controller import DataController
from features.airtime_data.network_detector import NetworkDetector
from widgets import GlassCard


Builder.load_file(str(Path(__file__).with_name("data_screen.kv")))


class DataPackageCard(ButtonBehavior, GlassCard):
    package_id = StringProperty("")
    title = StringProperty("")
    summary = StringProperty("")
    price_text = StringProperty("")
    selected = BooleanProperty(False)
    callback = ObjectProperty(None, allownone=True)

    def on_selected(self, *_):
        if self.selected:
            self.md_bg_color = (0.18, 0.14, 0.02, 1)
            self.line_color = (1, 0.76, 0.12, 1)
        else:
            self.md_bg_color = (0.10, 0.10, 0.10, 1)
            self.line_color = (0.20, 0.20, 0.20, 1)

    def on_release(self):
        if callable(self.callback):
            self.callback(self.package_id)


class DataScreen(MDScreen):
    loading = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = DataController()
        self.selected_package = None
        self._last_network = "Unknown"
        self._packages = {}

    def on_enter(self):
        self._set_wallet_balance()
        self._update_network_and_packages()

    def _set_wallet_balance(self):
        app = MDApp.get_running_app()
        balance = 0.0
        if app and getattr(app, "app_state", None):
            wallet = getattr(app.app_state, "wallet", None)
            if isinstance(wallet, dict):
                balance = float(wallet.get("balance") or 0.0)
            elif wallet is not None:
                balance = float(getattr(wallet, "balance", 0.0) or 0.0)
        if "balance_label" in self.ids:
            self.ids.balance_label.text = f"GHS {balance:,.2f}"

    def on_phone_text(self, value):
        self._update_network_and_packages(value)

    def _update_network_and_packages(self, phone_value=""):
        detected = NetworkDetector.detect(phone_value)
        if "network" in self.ids:
            self.ids.network.text = detected
        if detected != self._last_network:
            self._last_network = detected
            if detected != "Unknown":
                self.load_packages(detected)
            else:
                self._set_packages([])

    def load_packages(self, network):
        Thread(target=self._load_packages_worker, args=(network,), daemon=True).start()

    def _load_packages_worker(self, network):
        try:
            packages = self.controller.load_packages(network)
        except Exception as exc:
            Clock.schedule_once(lambda dt, msg=str(exc): self.show_message(msg or "Unable to load packages."))
            return

        Clock.schedule_once(lambda dt, res=packages: self._set_packages(res))

    def _set_packages(self, packages):
        normalized = []
        self._packages = {}
        for item in packages:
            package_id = str(item.get("package_id") or item.get("id") or item.get("code") or "").strip()
            if not package_id:
                continue
            item = dict(item)
            item["package_id"] = package_id
            self._packages[package_id] = item
            normalized.append(item)

        if "package_list" in self.ids:
            self.ids.package_list.data = [
                {
                    "package_id": item["package_id"],
                    "title": item.get("title") or item.get("name") or "Package",
                    "summary": item.get("description") or item.get("summary") or "",
                    "price_text": item.get("price_text") or f"GHS {float(item.get('price') or 0.0):,.2f}",
                    "callback": self.select_package,
                    "selected": item["package_id"] == self.selected_package,
                }
                for item in normalized
            ]
        if "selected_package_label" in self.ids:
            self.ids.selected_package_label.text = self._selected_summary()

    def _selected_summary(self):
        if not self.selected_package or self.selected_package not in self._packages:
            return "No package selected"
        package = self._packages.get(self.selected_package, {})
        title = package.get("title") or package.get("name") or "Package"
        price = float(package.get("price") or 0.0)
        return f"{title} - GHS {price:,.2f}"

    def select_package(self, package_id):
        if package_id not in self._packages:
            return
        self.selected_package = package_id
        self._set_packages(list(self._packages.values()))

    def submit_purchase(self):
        if self.loading:
            return

        phone = self.ids.phone.text.strip()
        network = self.ids.network.text.strip()
        package = self._packages.get(self.selected_package)
        if package is None:
            self.show_message("Select a package first.")
            return

        self._set_loading(True)
        Thread(target=self._submit_worker, args=(phone, package, network), daemon=True).start()

    def _set_loading(self, value: bool) -> None:
        self.loading = bool(value)
        button = self.ids.get("purchase_button")
        if button is not None:
            button.loading = bool(value)

    def _submit_worker(self, phone, package, network):
        try:
            result = self.controller.purchase(phone, package, network)
        except Exception as exc:
            Clock.schedule_once(
                lambda dt, msg=str(exc): self._finish_purchase_request(msg or "Data purchase failed.")
            )
            return

        Clock.schedule_once(lambda dt, res=result: self._apply_purchase_result(res))

    def _finish_purchase_request(self, message: str) -> None:
        self._set_loading(False)
        self.show_message(message)

    def _apply_purchase_result(self, result: dict) -> None:
        try:
            self.show_message(self._success_text(result))
            self._publish_event("TransactionCreated", result)
            self._publish_event("WalletUpdated", result)
        finally:
            self._set_loading(False)

    @staticmethod
    def _success_text(result):
        if isinstance(result, dict):
            reference = result.get("reference") or result.get("transaction_id") or ""
            if reference:
                return f"Data purchase successful. Ref: {reference}"
        return "Data purchase successful."

    def _publish_event(self, event_name, payload):
        app = MDApp.get_running_app()
        event_bus = getattr(app, "event_bus", None) if app else None
        publish = getattr(event_bus, "publish", None)
        if callable(publish):
            publish(event_name, payload=payload)

    def show_message(self, text):
        show_app_snackbar(text)
