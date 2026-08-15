from pathlib import Path
from threading import Thread

from kivy.clock import Clock
from kivy.lang import Builder
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.snackbar import MDSnackbar
from kivymd.uix.snackbar import MDSnackbarText

from features.bitcoin.bitcoin_controller import BitcoinController


Builder.load_file(str(Path(__file__).with_name("bitcoin_screen.kv")))


class BitcoinScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = BitcoinController()
        self._price_event = None
        self._current_wallet = {}
        self._current_price = 0.0

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
        Thread(target=self._load_dashboard_worker, daemon=True).start()

    def _load_dashboard_worker(self):
        try:
            data = self.controller.load_dashboard()
        except Exception as exc:
            Clock.schedule_once(lambda dt: self.show_message(str(exc) or "Unable to load Bitcoin wallet."))
            return

        Clock.schedule_once(lambda dt: self.update_ui(data))

    def refresh_price(self, *_):
        Thread(target=self._refresh_price_worker, daemon=True).start()

    def _refresh_price_worker(self):
        try:
            payload = self.controller.refresh_price()
        except Exception:
            return
        Clock.schedule_once(lambda dt: self.update_price(payload))

    def update_ui(self, data):
        self._current_wallet = data.get("wallet")
        self._current_price = float(data.get("price") or 0.0)

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
            self.ids.transaction_list.data = data.get("transactions", [])

    def update_price(self, payload):
        self._current_price = float(payload.get("price") or 0.0)
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
            Clock.schedule_once(lambda dt: self.show_message(str(exc) or "Unable to create deposit address."))
            return

        address = ""
        if isinstance(payload, dict):
            address = payload.get("address") or payload.get("deposit_address") or ""
        message = f"Deposit address ready: {address}" if address else "Deposit address ready."
        Clock.schedule_once(lambda dt: self.show_message(message))

    def withdraw_btc(self):
        self.show_message("BTC withdrawal flow will open from the backend form.")

    def show_message(self, text):
        MDSnackbar(MDSnackbarText(text=str(text or ""))).open()
