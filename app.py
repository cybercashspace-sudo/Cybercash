import logging
import os

from kivy.properties import ColorProperty, StringProperty
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, SlideTransition
from kivymd.app import MDApp

from core.theme_manager import ThemeManager
from screens.splash import SplashScreen
from screens.login import LoginScreen
from screens.register import RegisterScreen
from screens.otp import OTPScreen
from screens.home import HomeScreen
from screens.dashboard import DashboardScreen
from screens.wallet import DepositScreen, WalletScreen, WithdrawScreen
from screens.p2p_transfer import P2PTransferScreen
from screens.agent import AgentScreen
from screens.airtime import AirtimeScreen
from screens.data_bundle import DataBundleScreen
from screens.airtime_cash import AirtimeCashScreen
from screens.loans import LoanScreen
from screens.investments import InvestmentScreen
from screens.escrow import EscrowScreen
from screens.cards import CardScreen
from screens.btc import BTCScreen
from screens.pay_bills import PayBillsScreen
from screens.transactions import TransactionScreen
from screens.settings import SettingsScreen
from screens.admin_dashboard import AdminDashboardScreen
from screens.admin_withdrawals import AdminWithdrawalsScreen
from screens.admin_agents import AdminAgentsScreen
from screens.admin_users import AdminUsersScreen
from screens.admin_transactions import AdminTransactionsScreen
from screens.admin_revenue import AdminRevenueScreen
from screens.admin_fraud_alerts import AdminFraudAlertsScreen
from storage import get_token
from theme import CyberTheme

# Prevent third-party logging formatting failures from flooding stderr and freezing UI.
logging.raiseExceptions = False
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)


class AppScreenManager(ScreenManager):
    previous_screen = StringProperty("")
    _last_screen = ""

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

    def build(self):
        theme_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kivy_frontend", "ui_theme.kv")
        if os.path.exists(theme_path):
            Builder.load_file(theme_path)
        self.theme_cls.theme_style = "Dark"
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
        sm.add_widget(LoginScreen(name="login"))
        sm.add_widget(RegisterScreen(name="register"))
        sm.add_widget(OTPScreen(name="otp"))
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(DashboardScreen(name="dashboard"))
        sm.add_widget(WalletScreen(name="wallet"))
        sm.add_widget(DepositScreen(name="deposit"))
        sm.add_widget(WithdrawScreen(name="withdraw"))
        sm.add_widget(P2PTransferScreen(name="p2p_transfer"))
        sm.add_widget(AgentScreen(name="agent"))
        sm.add_widget(AirtimeScreen(name="airtime"))
        sm.add_widget(DataBundleScreen(name="data_bundle"))
        sm.add_widget(AirtimeCashScreen(name="airtime_2_cash"))
        sm.add_widget(LoanScreen(name="loans"))
        sm.add_widget(InvestmentScreen(name="investments"))
        sm.add_widget(EscrowScreen(name="escrow"))
        sm.add_widget(CardScreen(name="cards"))
        sm.add_widget(BTCScreen(name="btc"))
        sm.add_widget(PayBillsScreen(name="pay_bills"))
        sm.add_widget(TransactionScreen(name="transactions"))
        sm.add_widget(SettingsScreen(name="settings"))
        sm.add_widget(AdminDashboardScreen(name="admin_dashboard"))
        sm.add_widget(AdminWithdrawalsScreen(name="admin_withdrawals"))
        sm.add_widget(AdminAgentsScreen(name="admin_agents"))
        sm.add_widget(AdminUsersScreen(name="admin_users"))
        sm.add_widget(AdminTransactionsScreen(name="admin_transactions"))
        sm.add_widget(AdminRevenueScreen(name="admin_revenue"))
        sm.add_widget(AdminFraudAlertsScreen(name="admin_fraud_alerts"))

        # Skip the splash for returning users who already have a token. Keep the splash
        # only as the pre-auth screen before showing Login.
        if self.access_token and sm.has_screen("home"):
            sm.current = "home"
        elif sm.has_screen("splash"):
            sm.current = "splash"
        elif sm.has_screen("login"):
            sm.current = "login"

        return sm
