from __future__ import annotations

from threading import Thread
from pathlib import Path

from kivy.clock import Clock
from kivy.properties import BooleanProperty, StringProperty
from kivy.lang import Builder
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from components.app_snackbar import show_app_snackbar
from core.exceptions import NetworkError, ValidationError
from features.auth.animations import AuthAnimations
from features.withdrawal.withdrawal_controller import WithdrawalController


Builder.load_file(str(Path(__file__).with_name("withdrawal_screen.kv")))


class WithdrawalScreen(MDScreen):
    loading = BooleanProperty(False)
    selected_network = StringProperty("auto")
    detected_network = StringProperty("Auto")
    pending_withdrawal_id = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = WithdrawalController()

    def on_enter(self):
        Clock.schedule_once(self.start_animation, 0.08)

    def start_animation(self, *_args):
        AuthAnimations.enter(self.ids.get("title_block"), 0.00, 0.35)
        AuthAnimations.slide(self.ids.get("amount_card"), 0.10, 24, 0.40)
        AuthAnimations.slide(self.ids.get("network_card"), 0.18, 24, 0.40)
        AuthAnimations.slide(self.ids.get("details_card"), 0.26, 24, 0.40)
        AuthAnimations.pop(self.ids.get("withdraw_button"), 0.34, 0.30)

    def set_network(self, network: str):
        self.selected_network = str(network or "auto").strip().lower()

    def update_detected_network(self):
        phone = str(self.ids.phone.text or "").strip()
        detected = self.controller.detect_network(phone)
        self.detected_network = detected.upper() if detected != "auto" else "AUTO"
        if self.selected_network == "auto":
            self.detected_network = detected.upper() if detected != "auto" else "AUTO"

    def submit_withdrawal(self):
        if self.loading:
            return

        amount = str(self.ids.amount.text or "").strip()
        network = self.selected_network
        phone = str(self.ids.phone.text or "").strip()
        pin = str(self.ids.pin.text or "").strip()

        self._set_loading(True)
        Thread(target=self._withdraw_worker, args=(amount, network, phone, pin), daemon=True).start()

    def _set_loading(self, value: bool) -> None:
        self.loading = bool(value)
        button = self.ids.get("withdraw_button")
        if button is not None:
            button.loading = bool(value)

    def _withdraw_worker(self, amount: str, network: str, phone: str, pin: str) -> None:
        try:
            result = self.controller.withdraw(amount, network, phone, pin)
        except (ValidationError, NetworkError) as exc:
            Clock.schedule_once(lambda _dt, msg=str(exc): self._finish_withdrawal_request(msg))
            return
        except Exception:
            Clock.schedule_once(lambda _dt: self._finish_withdrawal_request("Withdrawal failed."))
            return

        Clock.schedule_once(lambda _dt, res=result: self._apply_withdrawal_result(res))

    def _finish_withdrawal_request(self, message: str) -> None:
        self._set_loading(False)
        self.show_message(message)

    def _apply_withdrawal_result(self, result: dict) -> None:
        try:
            self._handle_success(result)
        finally:
            self._set_loading(False)

    def _handle_success(self, result: dict):
        app = MDApp.get_running_app()
        if app is not None and hasattr(app, "event_bus"):
            try:
                app.event_bus.publish("WalletUpdated", result)
                app.event_bus.publish("TransactionCreated", result)
            except Exception:
                pass
        if app is not None and hasattr(app, "go_to_screen"):
            app.go_to_screen("home", fallback="withdraw", transition_style="slide_right")
        self.show_message("Withdrawal submitted.")

    def show_message(self, text: str):
        show_app_snackbar(text)
