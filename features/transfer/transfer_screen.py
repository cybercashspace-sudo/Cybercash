from __future__ import annotations

from pathlib import Path
from threading import Thread

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import BooleanProperty, StringProperty
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from components.app_snackbar import show_app_snackbar
from core.exceptions import NetworkError, ValidationError
from features.auth.animations import AuthAnimations
from features.transfer.transfer_controller import TransferController


Builder.load_file(str(Path(__file__).with_name("transfer_screen.kv")))


class TransferScreen(MDScreen):
    loading = BooleanProperty(False)
    recipient_preview = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = TransferController()

    def on_enter(self):
        Clock.schedule_once(self.start_animation, 0.08)

    def start_animation(self, *_args):
        AuthAnimations.enter(self.ids.get("title_block"), 0.00, 0.35)
        AuthAnimations.slide(self.ids.get("recipient_card"), 0.10, 24, 0.40)
        AuthAnimations.slide(self.ids.get("transfer_card"), 0.18, 24, 0.40)
        AuthAnimations.pop(self.ids.get("send_button"), 0.28, 0.30)

    def lookup_recipient(self):
        identifier = str(self.ids.recipient.text or "").strip()
        if not identifier:
            self.recipient_preview = ""
            return

        Thread(target=self._lookup_recipient_worker, args=(identifier,), daemon=True).start()

    def _lookup_recipient_worker(self, identifier: str) -> None:
        try:
            data = self.controller.lookup_recipient(identifier)
        except ValidationError as exc:
            Clock.schedule_once(lambda _dt, msg=str(exc): self._finish_lookup_failure(msg))
            return
        except Exception:
            Clock.schedule_once(lambda _dt: self._finish_lookup_failure("Unable to validate recipient."))
            return

        Clock.schedule_once(lambda _dt, res=data, ident=identifier: self._apply_recipient_lookup(res, ident))

    def _apply_recipient_lookup(self, data: dict, identifier: str) -> None:
        name = str(data.get("name") or data.get("full_name") or "").strip()
        wallet = str(data.get("wallet_id") or data.get("account_number") or data.get("identifier") or identifier).strip()
        self.recipient_preview = f"{name} - {wallet}" if name else wallet

    def _finish_lookup_failure(self, message: str) -> None:
        self.recipient_preview = ""
        self.show_message(message)

    def submit_transfer(self):
        if self.loading:
            return

        recipient = str(self.ids.recipient.text or "").strip()
        amount = str(self.ids.amount.text or "").strip()
        pin = str(self.ids.pin.text or "").strip()
        description = str(self.ids.description.text or "").strip()

        self._set_loading(True)
        Thread(target=self._transfer_worker, args=(recipient, amount, pin, description), daemon=True).start()

    def _set_loading(self, value: bool) -> None:
        self.loading = bool(value)
        button = self.ids.get("send_button")
        if button is not None:
            button.loading = bool(value)

    def _transfer_worker(self, recipient: str, amount: str, pin: str, description: str) -> None:
        try:
            result = self.controller.transfer(recipient, amount, pin, description=description)
        except (ValidationError, NetworkError) as exc:
            Clock.schedule_once(lambda _dt, msg=str(exc): self._finish_transfer_request(msg))
            return
        except Exception:
            Clock.schedule_once(lambda _dt: self._finish_transfer_request("Transfer failed."))
            return

        Clock.schedule_once(lambda _dt, res=result: self._apply_transfer_result(res))

    def _finish_transfer_request(self, message: str) -> None:
        self._set_loading(False)
        self.show_message(message)

    def _apply_transfer_result(self, result: dict) -> None:
        try:
            self._on_success(result)
        finally:
            self._set_loading(False)

    def _on_success(self, result: dict):
        app = MDApp.get_running_app()
        if app is not None and hasattr(app, "event_bus"):
            try:
                app.event_bus.publish("WalletUpdated", result)
                app.event_bus.publish("TransactionCreated", result)
            except Exception:
                pass
        if app is not None and hasattr(app, "go_to_screen"):
            app.go_to_screen("home", fallback="p2p_transfer", transition_style="slide_right")
        self.show_message("Transfer successful.")

    def show_message(self, text: str):
        show_app_snackbar(text)
