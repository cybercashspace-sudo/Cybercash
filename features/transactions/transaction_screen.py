from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Thread

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from core.pull_refresh import PullToRefreshMixin
from components.app_snackbar import show_app_snackbar
from core.dashboard_cache import save_dashboard_cache
from core.popup_manager import show_message_dialog
from core.session import session

from features.auth.animations import AuthAnimations
from features.transactions.transaction_controller import TransactionController
from core.refresh_mixin import RefreshableScreenMixin


Builder.load_file(str(Path(__file__).with_name("transaction_screen.kv")))


class TransactionScreen(PullToRefreshMixin, RefreshableScreenMixin, MDScreen):
    page = NumericProperty(1)
    page_size = NumericProperty(100)
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
        self._before_id: int | None = None
        self._owner_identity = ""
        self._history_generation = 0

    def on_enter(self):
        owner_identity = self._current_owner_identity()
        if owner_identity != self._owner_identity:
            self._owner_identity = owner_identity
            self._history_generation += 1
            self._all_transactions = []
            self.transactions = []
            self._before_id = None
            try:
                save_dashboard_cache(transactions=[])
            except Exception:
                pass
            if "transaction_list" in self.ids:
                self.ids.transaction_list.data = []
        Clock.schedule_once(self.start_animation, 0.08)
        self.refresh_transactions()

    @staticmethod
    def _current_owner_identity() -> str:
        try:
            user = session.get_user() or {}
        except Exception:
            user = {}
        if isinstance(user, dict):
            for key in ("id", "user_id", "email", "phone_number", "momo_number"):
                value = str(user.get(key) or "").strip().lower()
                if value:
                    return f"{key}:{value}"
        app = MDApp.get_running_app()
        token = str(getattr(app, "access_token", "") or "").strip()
        if token:
            import hashlib

            return "token:" + hashlib.sha256(token.encode("utf-8")).hexdigest()
        return "signed-out"

    def start_animation(self, *_args):
        AuthAnimations.enter(self.ids.get("title_block"), 0.00, 0.35)
        AuthAnimations.slide(self.ids.get("filter_card"), 0.10, 20, 0.40)
        AuthAnimations.slide(self.ids.get("list_card"), 0.18, 24, 0.40)

    def refresh_transactions(self):
        if self.loading:
            return
        self._history_generation += 1
        self.page = 1
        self._before_id = None
        self.has_more = True
        self._begin_refresh("Refreshing transactions...")
        self._sync_empty_state()
        self._start_transaction_worker(page=1, before_id=None, generation=self._history_generation)

    def load_more(self):
        if self.loading or not self.has_more:
            return
        cursor = self._oldest_transaction_id()
        if cursor is None:
            self.has_more = False
            return
        self.loading = True
        self._sync_empty_state()
        self._start_transaction_worker(
            page=self.page + 1,
            before_id=cursor,
            generation=self._history_generation,
        )

    def _start_transaction_worker(self, *, page: int, before_id: int | None, generation: int):
        worker = Thread(
            target=self._load_transactions_worker,
            args=(page, before_id, generation),
            daemon=True,
        )
        try:
            worker.start()
        except Exception:
            if page <= 1:
                self._fail_refresh("Unable to load transactions right now.")
            else:
                self._finish_loading()
            self.show_message("Unable to load transactions right now. Please try again.")

    def _load_transactions_worker(self, page: int, before_id: int | None, generation: int):
        try:
            rows = self.controller.load_transactions(before_id=before_id, limit=int(self.page_size))
            Clock.schedule_once(
                lambda _dt: self._apply_transactions(rows, page, generation)
            )
        except Exception:
            Clock.schedule_once(lambda _dt: self._handle_transactions_error(page, generation))

    def _apply_transactions(self, rows: list[dict], page: int, generation: int):
        if generation != self._history_generation or self._owner_identity != self._current_owner_identity():
            return
        if page <= 1:
            self._all_transactions = self.controller.merge_transactions(self._all_transactions, rows)
        else:
            self._all_transactions = self.controller.merge_transactions(rows, self._all_transactions)
        self.page = page
        self.has_more = len(rows) >= int(self.page_size)
        self._before_id = self._oldest_transaction_id()
        self.apply_view_filters()
        if page <= 1:
            self._complete_refresh("Transactions refreshed.")
        else:
            self._finish_loading()
        app = MDApp.get_running_app()
        if app is not None and hasattr(app, "app_state"):
            try:
                app.app_state.set_wallet(getattr(app.app_state, "wallet", None))
            except Exception:
                pass

    def _handle_transactions_error(self, page: int, generation: int):
        if generation != self._history_generation or self._owner_identity != self._current_owner_identity():
            return
        if page <= 1:
            self._fail_refresh("Unable to refresh transactions.")
            self.show_message("Unable to refresh transactions.")
            return
        self._finish_loading()

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
            self.ids.transaction_list.data = [
                {
                    **row,
                    "detail_callback": self.show_transaction_details,
                    "detail_data": self._transaction_detail_fields(row),
                }
                for row in rows
            ]
        self._sync_empty_state()

    def _oldest_transaction_id(self) -> int | None:
        ids = []
        for row in self._all_transactions:
            try:
                value = int(row.get("transaction_id") or 0)
            except (TypeError, ValueError):
                continue
            if value > 0:
                ids.append(value)
        return min(ids) if ids else None

    @staticmethod
    def _compact_detail(value, fallback: str = "Not available", limit: int = 120) -> str:
        cleaned = " ".join(str(value or "").split())
        return cleaned[:limit] if cleaned else fallback

    @staticmethod
    def _format_transaction_time(value: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            return "Not available"
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone().strftime("%d %b %Y, %I:%M %p")
        except (TypeError, ValueError, OverflowError):
            return raw[:80]

    def _transaction_detail_fields(self, row: dict) -> dict:
        app = MDApp.get_running_app()
        try:
            user = session.get_user() or {}
        except Exception:
            user = {}
        if not isinstance(user, dict):
            user = {}
        username = row.get("username") or user.get("full_name") or user.get("name")
        username = username or getattr(app, "user_name", "")
        momo = row.get("momo_number") or user.get("momo_number") or user.get("phone_number")
        try:
            amount = float(row.get("amount") or 0.0)
        except (TypeError, ValueError):
            amount = 0.0
        currency = self._compact_detail(row.get("currency") or "GHS", "GHS", 12)
        amount_text = f"{currency} {abs(amount):,.2f}"
        if amount < 0:
            amount_text = f"- {amount_text}"
        return {
            "Username": self._compact_detail(username, "Account holder"),
            "MoMo Number": self._compact_detail(momo),
            "Type and Amount": f"{self._compact_detail(row.get('type'), 'Transaction', 60)} - {amount_text}",
            "Time and Date": self._format_transaction_time(row.get("created_at", "")),
            "Reference": self._compact_detail(row.get("reference")),
            "Status": self._compact_detail(row.get("status"), "Unknown", 40),
        }

    def show_transaction_details(self, detail_fields: dict):
        if not isinstance(detail_fields, dict):
            return
        message = "\n\n".join(
            f"{label}: {self._compact_detail(detail_fields.get(label), 'Not available')}"
            for label in (
                "Username",
                "MoMo Number",
                "Type and Amount",
                "Time and Date",
                "Reference",
                "Status",
            )
        )
        show_message_dialog(self, title="Transaction details", message=message, close_label="Done")

    def set_filter(self, value: str):
        self.selected_filter = str(value or "all").strip().lower()
        self.apply_view_filters()

    def on_search_query(self, *_args):
        self.apply_view_filters()

    def on_scroll_y(self, instance, value, *args):
        if value <= 0.12 and self.has_more and not self.loading:
            self.load_more()

    def show_message(self, text: str):
        show_app_snackbar(text)

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
