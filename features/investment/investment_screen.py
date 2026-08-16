from pathlib import Path
from threading import Thread

from kivy.clock import Clock
from kivy.lang import Builder
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from components.app_snackbar import show_app_snackbar

from features.investment.investment_controller import InvestmentController


Builder.load_file(str(Path(__file__).with_name("investment_screen.kv")))


class InvestmentScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = InvestmentController()
        self.selected_days = 120
        self.available_balance = 0.0
        self._plans_by_days = {}
        self._history = []
        self._active_investment = None

    def on_enter(self):
        self._set_wallet_balance()
        self.load_dashboard()

    def _set_wallet_balance(self):
        app = MDApp.get_running_app()
        balance = 0.0
        if app and getattr(app, "app_state", None):
            wallet = getattr(app.app_state, "wallet", None)
            if isinstance(wallet, dict):
                balance = float(wallet.get("balance") or 0.0)
            elif wallet is not None:
                balance = float(getattr(wallet, "balance", 0.0) or 0.0)
        self.available_balance = balance
        if "available_balance" in self.ids:
            self.ids.available_balance.text = f"GH₵ {balance:,.2f}"

    def load_dashboard(self):
        Thread(target=self._load_worker, daemon=True).start()

    def _load_worker(self):
        try:
            data = self.controller.load_dashboard()
        except Exception as exc:
            Clock.schedule_once(lambda dt: self.show_message(str(exc) or "Unable to load investments."))
            return
        Clock.schedule_once(lambda dt: self.update_ui(data))

    def update_ui(self, data):
        self._plans_by_days = {item["plan_days"]: item for item in data.get("plans", [])}
        self._history = data.get("history", [])
        self._active_investment = data.get("active_investment")

        if "plan_list" in self.ids:
            self.ids.plan_list.data = [
                {
                    **item,
                    "callback": self.select_plan,
                    "selected": item["plan_days"] == self.selected_days,
                }
                for item in data.get("plans", [])
            ]

        if "history_list" in self.ids:
            self.ids.history_list.data = data.get("history", [])

        active = self._active_investment or {}
        if "active_amount" in self.ids:
            self.ids.active_amount.text = active.get("title", "GH₵ 0.00")
        if "active_plan" in self.ids:
            self.ids.active_plan.text = active.get("subtitle", "Plan: --")
        if "active_earned" in self.ids:
            self.ids.active_earned.text = active.get("detail", "Earned GH₵ 0.00")
        if "active_status" in self.ids:
            self.ids.active_status.text = active.get("status_text", "No active investment")
        if "investment_progress" in self.ids:
            self.ids.investment_progress.value = float(active.get("progress", 0) or 0)
        if "maturity_label" in self.ids:
            self.ids.maturity_label.text = active.get("created_at", "Maturity not available")

        self.update_preview()

    def on_amount_text(self, value):
        self.update_preview()

    def select_plan(self, days):
        if days:
            self.selected_days = int(days)
        self._refresh_plan_selection()
        self.update_preview()

    def _refresh_plan_selection(self):
        if "plan_list" in self.ids:
            self.ids.plan_list.data = [
                {
                    **item,
                    "callback": self.select_plan,
                    "selected": item["plan_days"] == self.selected_days,
                }
                for item in self._plans_by_days.values()
            ]
        if "selected_plan_label" in self.ids:
            self.ids.selected_plan_label.text = f"{self.selected_days} Days"

    def update_preview(self):
        amount_text = self.ids.amount.text.strip() if "amount" in self.ids else ""
        if not amount_text:
            daily = 0.0
            total = 0.0
        else:
            try:
                preview = self.controller.calculate_preview(amount_text, self.selected_days)
                daily = preview["daily"]
                total = preview["total"]
            except Exception:
                daily = 0.0
                total = 0.0

        if "daily_earning" in self.ids:
            self.ids.daily_earning.text = f"GH₵ {daily:,.2f}"
        if "total_earning" in self.ids:
            self.ids.total_earning.text = f"GH₵ {total:,.2f}"
        if "selected_plan_hint" in self.ids:
            plan = self._plans_by_days.get(self.selected_days, {})
            self.ids.selected_plan_hint.text = plan.get("detail", "Choose a plan to preview returns.")

    def start_investment(self):
        amount = self.ids.amount.text.strip() if "amount" in self.ids else ""
        purpose = self.ids.purpose.text.strip() if "purpose" in self.ids else ""
        Thread(target=self._start_worker, args=(amount, self.selected_days, purpose), daemon=True).start()

    def _start_worker(self, amount, days, purpose):
        try:
            result = self.controller.start_investment(
                amount,
                days,
                available_balance=self.available_balance,
                purpose=purpose,
            )
        except Exception as exc:
            Clock.schedule_once(lambda dt: self.show_message(str(exc) or "Investment could not be created."))
            return

        Clock.schedule_once(lambda dt: self.show_message(self._success_text(result)))
        Clock.schedule_once(lambda dt: self._publish_event("InvestmentCreated", result))
        Clock.schedule_once(lambda dt: self._publish_event("WalletUpdated", result))
        Clock.schedule_once(lambda dt: self._publish_event("TransactionCreated", result))

    @staticmethod
    def _success_text(result):
        if isinstance(result, dict):
            reference = result.get("reference") or result.get("transaction_id") or ""
            if reference:
                return f"Investment created. Ref: {reference}"
        return "Investment created successfully."

    def _publish_event(self, event_name, payload):
        app = MDApp.get_running_app()
        event_bus = getattr(app, "event_bus", None) if app else None
        publish = getattr(event_bus, "publish", None)
        if callable(publish):
            publish(event_name, payload=payload)

    def show_message(self, text):
        show_app_snackbar(text)
