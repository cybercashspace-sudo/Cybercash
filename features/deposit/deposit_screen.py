from __future__ import annotations

import webbrowser
from threading import Thread
from pathlib import Path

from kivy.clock import Clock
from kivy.properties import BooleanProperty, StringProperty
from kivy.lang import Builder
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from components.app_snackbar import show_app_snackbar
from core.exceptions import PaymentError, ValidationError
from features.auth.animations import AuthAnimations
from features.deposit.deposit_controller import DepositController


Builder.load_file(str(Path(__file__).with_name("deposit_screen.kv")))


class DepositScreen(MDScreen):
    loading = BooleanProperty(False)
    selected_method = StringProperty("paystack")
    pending_reference = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = DepositController()

    def on_enter(self):
        Clock.schedule_once(self.start_animation, 0.08)

    def start_animation(self, *_args):
        AuthAnimations.enter(self.ids.get("title_block"), 0.00, 0.35)
        AuthAnimations.slide(self.ids.get("amount_card"), 0.12, 24, 0.40)
        AuthAnimations.enter(self.ids.get("method_card"), 0.24, 0.30)
        AuthAnimations.pop(self.ids.get("continue_button"), 0.36, 0.30)

    def set_method(self, method: str):
        self.selected_method = str(method or "paystack").strip().lower()

    def submit_deposit(self):
        if self.loading:
            return

        amount_text = str(self.ids.amount.text or "").strip()
        method = self.selected_method

        self._set_loading(True)
        Thread(target=self._submit_worker, args=(amount_text, method), daemon=True).start()

    def _set_loading(self, value: bool) -> None:
        self.loading = bool(value)
        button = self.ids.get("continue_button")
        if button is not None:
            button.loading = bool(value)

    def _submit_worker(self, amount_text: str, method: str) -> None:
        try:
            result = self.controller.start_deposit(amount_text, method)
        except (ValidationError, PaymentError) as exc:
            Clock.schedule_once(lambda _dt, msg=str(exc): self._finish_deposit_request(msg))
            return
        except Exception:
            Clock.schedule_once(lambda _dt: self._finish_deposit_request("Unable to start deposit."))
            return

        Clock.schedule_once(lambda _dt, res=result: self._apply_deposit_result(res))

    def _finish_deposit_request(self, message: str) -> None:
        self._set_loading(False)
        self.show_message(message)

    def _apply_deposit_result(self, result: dict) -> None:
        try:
            self.open_payment(result)
        finally:
            self._set_loading(False)

    def open_payment(self, result: dict):
        if not isinstance(result, dict):
            self.show_message("Deposit started.")
            return

        self.pending_reference = str(result.get("reference") or result.get("data", {}).get("reference") or "").strip()
        authorization_url = str(result.get("authorization_url") or result.get("data", {}).get("authorization_url") or "").strip()

        if authorization_url:
            webbrowser.open(authorization_url)
            self.show_message("Complete payment in the provider window.")
            return

        if self.pending_reference:
            self.show_message("Payment request created.")
            return

        self.show_message("Deposit request created.")

    def verify_pending_payment(self):
        if not self.pending_reference:
            self.show_message("No pending deposit to verify.")
            return

        Thread(target=self._verify_payment_worker, args=(self.pending_reference,), daemon=True).start()

    def _verify_payment_worker(self, reference: str) -> None:
        try:
            response = self.controller.verify_payment(reference)
        except Exception:
            Clock.schedule_once(lambda _dt: self.show_message("Unable to verify deposit right now."))
            return

        Clock.schedule_once(lambda _dt, res=response: self._apply_verification_result(res))

    def _apply_verification_result(self, response: dict) -> None:
        status = str(response.get("status", "") or "").strip().lower() if isinstance(response, dict) else ""
        if status in {"verified", "success", "completed"}:
            self._mark_success(response)
            return
        self.show_message("Payment is still pending.")

    def _mark_success(self, response: dict):
        app = MDApp.get_running_app()
        if app is not None and hasattr(app, "event_bus"):
            try:
                app.event_bus.publish("WalletUpdated", response)
                app.event_bus.publish("TransactionCreated", response)
            except Exception:
                pass
        if app is not None and hasattr(app, "go_to_screen"):
            app.go_to_screen("home", fallback="deposit", transition_style="slide_right")
        self.show_message("Deposit successful.")

    def show_message(self, text: str):
        show_app_snackbar(text)
