from pathlib import Path
from threading import Thread

from kivy.clock import Clock
from kivy.lang import Builder
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from core.pull_refresh import PullToRefreshMixin
from components.app_snackbar import show_app_snackbar

from features.bitcoin.bitcoin_controller import BitcoinController


Builder.load_file(str(Path(__file__).with_name("bitcoin_screen.kv")))


class BitcoinScreen(PullToRefreshMixin, MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = BitcoinController()
        self._price_event = None
        self._current_wallet = {}
        self._current_price = 0.0
        self.loading = False
        self._price_loading = False

    @staticmethod
    def _wallet_balance_value(wallet) -> float:
        if isinstance(wallet, dict):
            try:
                return float(wallet.get("balance") or 0.0)
            except Exception:
                return 0.0
        if wallet is not None:
            try:
                return float(getattr(wallet, "balance", 0.0) or 0.0)
            except Exception:
                return 0.0
        return 0.0

    def on_enter(self):
        self.load_dashboard()
        if self._price_event is None:
            self._price_event = Clock.schedule_interval(self.refresh_price, 30)

    def on_leave(self):
        if self._price_event is not None:
            self._price_event.cancel()
            self._price_event = None

    def load_dashboard(self):
        if self.loading:
            return
        self.loading = True
        Thread(target=self._load_dashboard_worker, daemon=True).start()

    def _load_dashboard_worker(self):
        try:
            data = self.controller.load_dashboard()
        except Exception as exc:
            message = str(exc) or "Unable to load Bitcoin wallet."
            Clock.schedule_once(lambda dt, error=message: self._finish_dashboard_error(error))
            return

        Clock.schedule_once(lambda dt: self._apply_dashboard_data(data))

    def refresh_price(self, *_):
        if self._price_loading:
            return
        self._price_loading = True
        Thread(target=self._refresh_price_worker, daemon=True).start()

    def _refresh_price_worker(self):
        try:
            payload = self.controller.refresh_price()
        except Exception:
            self._price_loading = False
            return
        Clock.schedule_once(lambda dt: self._apply_price_data(payload))

    def _apply_dashboard_data(self, data):
        try:
            if not isinstance(data, dict):
                raise ValueError("Bitcoin wallet data could not be read.")
            self.update_ui(data)
        except Exception:
            self._finish_dashboard_error("Unable to display Bitcoin wallet. Please refresh again.")

    def _finish_dashboard_error(self, message):
        self.loading = False
        self.show_message(message)
        self._finish_pull_refresh()

    def update_ui(self, data):
        self._current_wallet = data.get("wallet")
        try:
            self._current_price = float(data.get("price") or 0.0)
        except (TypeError, ValueError):
            self._current_price = 0.0

        if "wallet_balance" in self.ids:
            self.ids.wallet_balance.text = data.get("wallet_balance_text", "₿ 0.000000")
        if "wallet_usd" in self.ids:
            self.ids.wallet_usd.text = data.get("wallet_usd_text", "≈ GH₵ 0.00")
        if "btc_price" in self.ids:
            self.ids.btc_price.text = data.get("price_text", "$0.00")
        if "wallet_address" in self.ids:
            self.ids.wallet_address.text = data.get("wallet_address", "Not available")
        if "wallet_status" in self.ids:
            self.ids.wallet_status.text = data.get("wallet_status", "Active")
        if "transaction_list" in self.ids:
            rows = data.get("transactions", [])
            self.ids.transaction_list.data = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
        self.loading = False
        self._finish_pull_refresh()

    def _apply_price_data(self, payload):
        try:
            self.update_price(payload)
        except Exception:
            self.show_message("Bitcoin price could not be updated. Please try again.")
        finally:
            self._price_loading = False

    def update_price(self, payload):
        if not isinstance(payload, dict):
            return
        try:
            self._current_price = float(payload.get("price") or 0.0)
        except (TypeError, ValueError):
            self._current_price = 0.0
        if "btc_price" in self.ids:
            self.ids.btc_price.text = payload.get("price_text", "$0.00")

        if self._current_wallet and "wallet_usd" in self.ids:
            balance = self._wallet_balance_value(self._current_wallet)
            value = balance * self._current_price
            self.ids.wallet_usd.text = f"≈ GH₵ {value:,.2f}"

    def buy_btc(self):
        self.show_message("BTC buy flow will open from the backend form.")

    def sell_btc(self):
        self.show_message("BTC sell flow will open from the backend form.")

    def deposit_btc(self):
        Thread(target=self._deposit_worker, daemon=True).start()

    def _deposit_worker(self):
        try:
            payload = self.controller.create_deposit_address()
        except Exception as exc:
            message = str(exc) or "Unable to create deposit address."
            Clock.schedule_once(lambda dt, error=message: self.show_message(error))
            return

        address = ""
        if isinstance(payload, dict):
            address = payload.get("address") or payload.get("deposit_address") or ""
        message = f"Deposit address ready: {address}" if address else "Deposit address ready."
        Clock.schedule_once(lambda dt: self.show_message(message))

    def withdraw_btc(self):
        self.show_message("BTC withdrawal flow will open from the backend form.")

    def show_message(self, text):
        show_app_snackbar(text)
