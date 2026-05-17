import logging
import os
import threading
from importlib import import_module

# Android 14+ can emit noisy SDL HID receiver errors while probing gamepads.
os.environ.setdefault("SDL_HINT_JOYSTICK_HIDAPI", "0")

from kivy.clock import Clock
from kivy.properties import ColorProperty, StringProperty
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, SlideTransition
from kivymd.app import MDApp

from core.kivymd_compat import (
    install_kivymd_font_style_compat,
    register_font_style_aliases,
)
from core.theme_manager import ThemeManager

install_kivymd_font_style_compat()

from screens.splash import SplashScreen
from storage import get_token
from theme import CyberTheme

# Prevent third-party logging formatting failures from flooding stderr and freezing UI.
logging.raiseExceptions = False
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)


SCREEN_SPECS = {
    "login": ("screens.login", "LoginScreen"),
    "register": ("screens.register", "RegisterScreen"),
    "otp": ("screens.otp", "OTPScreen"),
    "home": ("screens.home", "HomeScreen"),
    "dashboard": ("screens.dashboard", "DashboardScreen"),
    "wallet": ("screens.wallet", "WalletScreen"),
    "deposit": ("screens.wallet", "DepositScreen"),
    "withdraw": ("screens.wallet", "WithdrawScreen"),
    "p2p_transfer": ("screens.p2p_transfer", "P2PTransferScreen"),
    "agent": ("screens.agent", "AgentScreen"),
    "airtime": ("screens.airtime", "AirtimeScreen"),
    "data_bundle": ("screens.data_bundle", "DataBundleScreen"),
    "airtime_2_cash": ("screens.airtime_cash", "AirtimeCashScreen"),
    "loans": ("screens.loans", "LoanScreen"),
    "investments": ("screens.investments", "InvestmentScreen"),
    "escrow": ("screens.escrow", "EscrowScreen"),
    "cards": ("screens.cards", "CardScreen"),
    "btc": ("screens.btc", "BTCScreen"),
    "pay_bills": ("screens.pay_bills", "PayBillsScreen"),
    "transactions": ("screens.transactions", "TransactionScreen"),
    "settings": ("screens.settings", "SettingsScreen"),
    "admin_dashboard": ("screens.admin_dashboard", "AdminDashboardScreen"),
    "admin_withdrawals": ("screens.admin_withdrawals", "AdminWithdrawalsScreen"),
    "admin_agents": ("screens.admin_agents", "AdminAgentsScreen"),
    "admin_users": ("screens.admin_users", "AdminUsersScreen"),
    "admin_transactions": ("screens.admin_transactions", "AdminTransactionsScreen"),
    "admin_revenue": ("screens.admin_revenue", "AdminRevenueScreen"),
    "admin_fraud_alerts": ("screens.admin_fraud_alerts", "AdminFraudAlertsScreen"),
}

FEATURE_SCREEN_ORDER = (
    "home",
    "dashboard",
    "wallet",
    "deposit",
    "withdraw",
    "p2p_transfer",
    "transactions",
    "settings",
    "cards",
    "escrow",
    "btc",
    "agent",
    "airtime",
    "data_bundle",
    "airtime_2_cash",
    "pay_bills",
    "loans",
    "investments",
    "admin_dashboard",
    "admin_withdrawals",
    "admin_agents",
    "admin_users",
    "admin_transactions",
    "admin_revenue",
    "admin_fraud_alerts",
)


class AppScreenManager(ScreenManager):
    previous_screen = StringProperty("")
    _last_screen = ""

    def has_screen(self, name):
        if super().has_screen(name):
            return True
        app = MDApp.get_running_app()
        ensure_screen = getattr(app, "ensure_screen", None)
        return bool(ensure_screen and ensure_screen(str(name or "")))

    def on_current(self, _instance, value):
        super().on_current(_instance, value)
        current = str(value or "")
        if self._last_screen and self._last_screen != current:
            self.previous_screen = self._last_screen
        self._last_screen = current


class CyberCashApp(MDApp):
    theme_mode = StringProperty("Dark")
    gold = ColorProperty(CyberTheme.GOLD)
    emerald = ColorProperty(CyberTheme.EMERALD)
    dark_bg = ColorProperty(CyberTheme.DARK_BG)
    card_bg = ColorProperty(CyberTheme.CARD_BG)
    success = ColorProperty(CyberTheme.SUCCESS)
    error = ColorProperty(CyberTheme.ERROR)
    btc = ColorProperty(CyberTheme.BTC)
    ui_background = ColorProperty([0.03, 0.05, 0.08, 1])
    ui_surface = ColorProperty([0.08, 0.10, 0.13, 0.96])
    ui_surface_soft = ColorProperty([0.11, 0.14, 0.18, 0.96])
    ui_glass = ColorProperty([1, 1, 1, 0.05])
    ui_glass_border = ColorProperty([1, 1, 1, 0.10])
    ui_overlay = ColorProperty([0.03, 0.03, 0.05, 0.90])
    ui_text_primary = ColorProperty([0.96, 0.96, 0.98, 1])
    ui_text_secondary = ColorProperty([0.74, 0.76, 0.80, 1])
    _deferred_screens_started = False
    _warmup_started = False
    _loading_screen_name = ""

    def apply_theme_palette(self, palette: dict) -> None:
        self.theme_mode = str(palette.get("mode", "Dark"))
        self.gold = list(palette.get("gold", CyberTheme.GOLD))
        self.emerald = list(palette.get("emerald", CyberTheme.EMERALD))
        self.dark_bg = list(palette.get("dark_bg", CyberTheme.DARK_BG))
        self.card_bg = list(palette.get("card_bg", CyberTheme.CARD_BG))
        self.success = list(palette.get("success", CyberTheme.SUCCESS))
        self.error = list(palette.get("error", CyberTheme.ERROR))
        self.btc = list(palette.get("btc", CyberTheme.BTC))
        self.ui_background = list(palette.get("bg_normal", palette.get("bg", self.ui_background)))
        self.ui_surface = list(palette.get("surface", self.ui_surface))
        self.ui_surface_soft = list(palette.get("surface_soft", self.ui_surface_soft))
        self.ui_glass = list(palette.get("glass", self.ui_glass))
        self.ui_glass_border = list(palette.get("glass_border", self.ui_glass_border))
        self.ui_overlay = list(palette.get("overlay", self.ui_overlay))
        self.ui_text_primary = list(palette.get("text_primary", self.ui_text_primary))
        self.ui_text_secondary = list(palette.get("text_secondary", self.ui_text_secondary))

    def toggle_theme(self):
        if self.theme_manager:
            self.theme_manager.toggle()

    def _warm_backend(self) -> None:
        try:
            from api.client import api_client

            api_client.warmup()
        except Exception:
            pass

    @staticmethod
    def _screen_exists(sm: ScreenManager, screen_name: str) -> bool:
        return any(
            str(getattr(screen, "name", "") or "") == str(screen_name or "")
            for screen in getattr(sm, "screens", [])
        )

    def ensure_screen(self, screen_name: str) -> bool:
        screen_name = str(screen_name or "").strip()
        sm = getattr(self, "root", None)
        if not screen_name or not sm:
            return False
        if self._screen_exists(sm, screen_name):
            return True
        if self._loading_screen_name == screen_name:
            return False

        spec = SCREEN_SPECS.get(screen_name)
        if not spec:
            return False

        module_name, class_name = spec
        self._loading_screen_name = screen_name
        try:
            module = import_module(module_name)
            screen_cls = getattr(module, class_name)
            sm.add_widget(screen_cls(name=screen_name))
            return True
        except Exception:
            logging.exception("Failed to load screen %s", screen_name)
            return False
        finally:
            self._loading_screen_name = ""

    def ensure_screens(self, screen_names) -> None:
        for screen_name in screen_names:
            self.ensure_screen(screen_name)

    def go_to_screen(self, screen_name: str, fallback: str = "login") -> bool:
        target = str(screen_name or "").strip()
        sm = getattr(self, "root", None)
        if sm and self.ensure_screen(target):
            sm.current = target
            return True
        if sm and fallback and self.ensure_screen(fallback):
            sm.current = fallback
            return True
        return False

    def complete_startup(self, *_args) -> None:
        sm = getattr(self, "root", None)
        if not sm:
            return

        target = "home" if self.access_token else "login"
        self.go_to_screen(target, fallback="login")

        if not self._deferred_screens_started:
            self._deferred_screens_started = True
            Clock.schedule_once(self._load_next_deferred_screen, 0.4)
        if not self._warmup_started:
            self._warmup_started = True
            threading.Thread(target=self._warm_backend, daemon=True).start()

    def _load_next_deferred_screen(self, *_args) -> None:
        for screen_name in FEATURE_SCREEN_ORDER:
            sm = getattr(self, "root", None)
            if not sm:
                return
            if not self._screen_exists(sm, screen_name):
                self.ensure_screen(screen_name)
                Clock.schedule_once(self._load_next_deferred_screen, 0.08)
                return

    def build(self):
        theme_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kivy_frontend", "ui_theme.kv")
        if os.path.exists(theme_path):
            Builder.load_file(theme_path)
        self.theme_cls.theme_style = "Dark"
        register_font_style_aliases(self.theme_cls.font_styles)
        # This KivyMD build errors on "Amber"; the app's gold styling comes from CyberTheme.
        self.theme_cls.primary_palette = "Green"
        self.pending_momo = ""
        self.access_token = get_token().strip()
        self.theme_mode = "Dark"
        self.gold = list(CyberTheme.GOLD)
        self.emerald = list(CyberTheme.EMERALD)
        self.dark_bg = list(CyberTheme.DARK_BG)
        self.card_bg = list(CyberTheme.CARD_BG)
        self.success = list(CyberTheme.SUCCESS)
        self.error = list(CyberTheme.ERROR)
        self.btc = list(CyberTheme.BTC)

        self.theme_manager = ThemeManager(self)
        self.theme_manager.apply(self.theme_mode, animate=False)

        sm = AppScreenManager(transition=SlideTransition(duration=0.3))
        sm.add_widget(SplashScreen(name="splash"))
        sm.current = "splash"

        return sm
