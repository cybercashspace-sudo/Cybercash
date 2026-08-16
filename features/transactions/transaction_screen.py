from __future__ import annotations

from pathlib import Path
from threading import Thread

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.snackbar import MDSnackbar, MDSnackbarText

from features.auth.animations import AuthAnimations
from features.transactions.transaction_controller import TransactionController


Builder.load_file(str(Path(__file__).with_name("transaction_screen.kv")))


class TransactionScreen(MDScreen):
    page = NumericProperty(1)
    page_size = NumericProperty(20)
    loading = BooleanProperty(False)
    has_more = BooleanProperty(True)
    has_transactions = BooleanProperty(False)
    show_empty_state = BooleanProperty(False)
    empty_state_icon = StringProperty("swap-horizontal")
    empty_state_title = StringProperty("No transactions yet")
    empty_state_message = StringProperty(
        "Your deposits, transfers, and withdrawals will appear here."
    )
    search_query = StringProperty("")
    selected_filter = StringProperty("all")
    transactions = ListProperty([])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = TransactionController()
        self._all_transactions: list[dict] = []
        self._recent_requests = 0

    def on_enter(self):
        Clock.schedule_once(self.start_animation, 0.08)
        self.refresh_transactions()

    def start_animation(self, *_args):
        AuthAnimations.enter(self.ids.get("title_block"), 0.00, 0.35)
        AuthAnimations.slide(self.ids.get("filter_card"), 0.10, 20, 0.40)
        AuthAnimations.slide(self.ids.get("list_card"), 0.18, 24, 0.40)

    def refresh_transactions(self):
        if self.loading:
            return
        self.page = 1
        self.has_more = True
        cached = self.controller.load_cached_transactions()
        if cached:
            self._all_transactions = cached
            self.apply_view_filters()
        self.loading = True
        self._sync_empty_state()
        Thread(target=self._load_transactions_worker, args=(1,), daemon=True).start()

    def load_more(self):
        if self.loading or not self.has_more:
            return
        self.loading = True
        self._sync_empty_state()
        Thread(target=self._load_transactions_worker, args=(self.page + 1,), daemon=True).start()

    def _load_transactions_worker(self, page: int):
        try:
            rows = self.controller.load_transactions(page=page, limit=int(self.page_size))
            Clock.schedule_once(lambda _dt: self._apply_transactions(rows, page))
        except Exception:
            Clock.schedule_once(lambda _dt: self._finish_loading())

    def _apply_transactions(self, rows: list[dict], page: int):
        if page <= 1:
            self._all_transactions = list(rows)
        else:
            self._all_transactions.extend(rows)
        self.page = page
        self.has_more = len(rows) >= int(self.page_size)
        self.apply_view_filters()
        self._finish_loading()
        app = MDApp.get_running_app()
        if app is not None and hasattr(app, "app_state"):
            try:
                app.app_state.set_wallet(getattr(app.app_state, "wallet", None))
            except Exception:
                pass

    def _finish_loading(self):
        self.loading = False
        self._sync_empty_state()

    def apply_view_filters(self):
        rows = self.controller.apply_filters(
            self._all_transactions,
            tx_type=self.selected_filter,
            query=self.search_query,
        )
        self.transactions = rows
        if "transaction_list" in self.ids:
            self.ids.transaction_list.data = rows
        self._sync_empty_state()

    def set_filter(self, value: str):
        self.selected_filter = str(value or "all").strip().lower()
        self.apply_view_filters()

    def on_search_query(self, *_args):
        self.apply_view_filters()

    def on_scroll_y(self, instance, value, *args):
        if value <= 0.12 and self.has_more and not self.loading:
            self.load_more()

    def show_message(self, text: str):
        MDSnackbar(MDSnackbarText(text=str(text or ""))).open()

    def _sync_empty_state(self):
        rows = list(self.transactions or [])
        self.has_transactions = bool(rows)
        active_filter = str(self.selected_filter or "all").strip().lower()
        query = str(self.search_query or "").strip()

        if self.has_transactions:
            self.show_empty_state = False
            return

        self.show_empty_state = not self.loading
        if query or active_filter != "all":
            self.empty_state_title = "No matching transactions"
            self.empty_state_message = (
                "Try a broader search or clear the filter to see all activity."
            )
        else:
            self.empty_state_title = "No transactions yet"
            self.empty_state_message = (
                "Your deposits, transfers, and withdrawals will appear here."
            )
