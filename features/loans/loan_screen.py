from pathlib import Path
from threading import Thread

from kivy.clock import Clock
from kivy.lang import Builder
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from components.app_snackbar import show_app_snackbar
from core.navigation import navigate

from features.loans.loan_controller import LoanController


Builder.load_file(str(Path(__file__).with_name("loan_screen.kv")))


class LoanScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = LoanController()
        self.selected_duration = 60
        self.available_credit = 0.0
        self._active_loan = None

    def on_enter(self):
        self.load_dashboard()

    def load_dashboard(self):
        Thread(target=self._load_worker, daemon=True).start()

    def _load_worker(self):
        try:
            data = self.controller.load_dashboard()
        except Exception as exc:
            Clock.schedule_once(lambda dt: self.show_message(str(exc) or "Unable to load loan dashboard."))
            return
        Clock.schedule_once(lambda dt: self.update_ui(data))

    def update_ui(self, data):
        self.available_credit = float(data.get("available_credit") or 0.0)
        self._active_loan = data.get("active_loan")

        if "available_credit" in self.ids:
            self.ids.available_credit.text = data.get("available_credit_text", "GH₵ 0.00")
        if "current_loan" in self.ids:
            self.ids.current_loan.text = data.get("current_loan_text", "GH₵ 0.00")
        if "loan_status" in self.ids:
            self.ids.loan_status.text = data.get("status_text", "Pending")
        if "next_payment" in self.ids:
            self.ids.next_payment.text = data.get("next_payment_text", "Not available")
        if "repayment_list" in self.ids:
            self.ids.repayment_list.data = data.get("repayments", [])
        self._update_duration_label()

    def select_duration(self, days):
        self.selected_duration = int(days)
        self._update_duration_label()

    def _update_duration_label(self):
        if "duration_label" in self.ids:
            self.ids.duration_label.text = f"{self.selected_duration} Days"

    def submit_application(self):
        amount = self.ids.amount.text.strip() if "amount" in self.ids else ""
        purpose = self.ids.purpose.text.strip() if "purpose" in self.ids else ""
        Thread(target=self._submit_worker, args=(amount, self.selected_duration, purpose), daemon=True).start()

    def _submit_worker(self, amount, duration, purpose):
        try:
            result = self.controller.apply_loan(amount, duration, purpose)
        except Exception as exc:
            Clock.schedule_once(lambda dt: self.show_message(str(exc) or "Loan application failed."))
            return

        Clock.schedule_once(lambda dt: self.show_message(self._success_text(result)))
        Clock.schedule_once(lambda dt: self._publish_event("LoanCreated", result))
        Clock.schedule_once(lambda dt: self._publish_event("WalletUpdated", result))
        Clock.schedule_once(lambda dt: self._publish_event("TransactionCreated", result))

    @staticmethod
    def _success_text(result):
        if isinstance(result, dict):
            reference = result.get("reference") or result.get("transaction_id") or ""
            if reference:
                return f"Loan application submitted. Ref: {reference}"
        return "Loan application submitted."

    def _publish_event(self, event_name, payload):
        app = MDApp.get_running_app()
        event_bus = getattr(app, "event_bus", None) if app else None
        publish = getattr(event_bus, "publish", None)
        if callable(publish):
            publish(event_name, payload=payload)

    def go_to_repayments(self):
        if self.manager and "loan_repayments" in self.manager.screen_names:
            navigate(self.manager, "loan_repayments", fallback="loans", transition_style="slide_left")
        else:
            self.show_message("Repayment history is not available yet.")

    def show_message(self, text):
        show_app_snackbar(text)
