from pathlib import Path
from threading import Thread

from kivy.clock import Clock
from kivy.lang import Builder
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from components.app_snackbar import show_app_snackbar

from features.airtime_data.airtime_controller import AirtimeController
from features.airtime_data.network_detector import NetworkDetector
from features.airtime_data.request_guard import RequestGuardMixin


Builder.load_file(str(Path(__file__).with_name("airtime_screen.kv")))


class AirtimeScreen(RequestGuardMixin, MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = AirtimeController()
        self._last_network = "Unknown"

    def on_enter(self):
        self._set_wallet_balance()
        self.detect_network(self.ids.phone.text if "phone" in self.ids else "")

    def on_leave(self, *_args):
        parent_on_leave = getattr(super(), "on_leave", None)
        if callable(parent_on_leave):
            parent_on_leave(*_args)
        self._last_network = "Unknown"

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

    def detect_network(self, phone):
        detected = NetworkDetector.detect(phone)
        if "network" in self.ids:
            self.ids.network.text = detected
        self._last_network = detected

    def submit_purchase(self):
        if self.loading:
            return

        phone = self.ids.phone.text.strip()
        amount = self.ids.amount.text.strip()
        network = self.ids.network.text.strip()
        self._set_loading(True)
        request_id = self._next_request_generation()
        Thread(target=self._submit_worker, args=(request_id, phone, amount, network), daemon=True).start()

    def _set_loading(self, value: bool) -> None:
        self.loading = bool(value)
        button = self.ids.get("purchase_button")
        if button is not None:
            button.loading = bool(value)

    def _submit_worker(self, request_id, phone, amount, network):
        try:
            result = self.controller.purchase(phone, amount, network)
        except Exception as exc:
            Clock.schedule_once(
                lambda dt, msg=str(exc), req=request_id: self._finish_purchase_request(req, msg or "Airtime purchase failed.")
            )
            return

        Clock.schedule_once(lambda dt, res=result, req=request_id: self._apply_purchase_result(req, res))

    def _finish_purchase_request(self, request_id: int, message: str) -> None:
        if not self._is_current_request(request_id):
            return
        self._set_loading(False)
        self.show_message(message)

    def _apply_purchase_result(self, request_id: int, result: dict) -> None:
        if not self._is_current_request(request_id):
            return
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
                return f"Airtime purchase successful. Ref: {reference}"
        return "Airtime purchase successful."

    def _publish_event(self, event_name, payload):
        app = MDApp.get_running_app()
        event_bus = getattr(app, "event_bus", None) if app else None
        publish = getattr(event_bus, "publish", None)
        if callable(publish):
            publish(event_name, payload=payload)

    def on_phone_text(self, value):
        self.detect_network(value)

    def show_message(self, text):
        show_app_snackbar(text)
