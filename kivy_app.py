import os
import threading
import logging
from importlib import import_module
from pathlib import Path

# Performance Tuning for Low-End Devices
from kivy.config import Config
Config.set('graphics', 'max_fps', '40')  # Balance between smoothness and battery
Config.set('graphics', 'multisamples', '0') # Disable anti-aliasing to save GPU cycles

# Android 14+ can emit noisy SDL HID receiver errors while probing gamepads.
os.environ.setdefault("SDL_JOYSTICK_HIDAPI", "0")
os.environ.setdefault("SDL_HINT_JOYSTICK_HIDAPI", "0")

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import BooleanProperty, ColorProperty, StringProperty
from kivy.uix.screenmanager import ScreenManager, NoTransition
from kivymd.app import MDApp

from kivy.utils import platform

from core.silent_touch import install_silent_touch
from components.transitions import smooth_switch_screen
from core.session import session
from core.event_bus import EventBus

install_silent_touch()

from core.kivymd_compat import (
    install_kivymd_font_style_compat,
    register_font_style_aliases,
)
from core.theme_manager import ThemeManager
from core.app_state import AppState

install_kivymd_font_style_compat()


def _install_snackbar_compat() -> None:
    try:
        snackbar_module = import_module("kivymd.uix.snackbar")
    except Exception:
        logging.exception("Failed to import KivyMD snackbar module for compatibility")
        return

    if hasattr(snackbar_module, "MDSnackbarText"):
        return

    def _snackbar_text(*args, **kwargs):
        try:
            from kivymd.uix.label import MDLabel as _SnackbarText
        except Exception:
            from kivy.uix.label import Label as _SnackbarText
        return _SnackbarText(*args, **kwargs)

    snackbar_module.MDSnackbarText = _snackbar_text


_install_snackbar_compat()

from features.notifications.notification_manager import notification_manager

from screens.splash import SplashScreen
from storage import (
    get_token,
    get_remember_me,
    clear_token,
    get_privacy_mode,
    save_privacy_mode,
)
from theme import CyberTheme

from kivy.cache import Cache

# Prevent third-party logging formatting failures from flooding stderr and freezing UI.
logging.raiseExceptions = False
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)


SCREEN_SPECS = {
    "login": ("screens.login", "LoginScreen"),
    "register": ("screens.register", "RegisterScreen"),
    "otp": ("screens.otp", "OTPScreen"),
    "reset_pin": ("screens.reset_pin", "ResetPinScreen"),
    "home": ("screens.home", "HomeScreen"),
    "wallet": ("screens.wallet", "WalletScreen"),
    "deposit": ("features.deposit.deposit_screen", "DepositScreen"),
    "withdraw": ("features.withdrawal.withdrawal_screen", "WithdrawalScreen"),
    "airtime": ("features.airtime_data.airtime_screen", "AirtimeScreen"),
    "data_bundle": ("features.airtime_data.data_screen", "DataScreen"),
    "p2p_transfer": ("features.transfer.transfer_screen", "TransferScreen"),
    "agent": ("screens.agent", "AgentScreen"),
    "airtime_2_cash": ("screens.airtime_cash", "AirtimeCashScreen"),
    "loans": ("screens.loans", "LoanScreen"),
    "investments": ("screens.investments", "InvestmentScreen"),
    "escrow": ("screens.escrow", "EscrowScreen"),
    "virtual_card": ("screens.cards", "VirtualCardScreen"),
    "btc": ("features.bitcoin.bitcoin_screen", "BitcoinScreen"),
    "bitcoin": ("features.bitcoin.bitcoin_screen", "BitcoinScreen"),
    "pay_bills": ("screens.pay_bills", "PayBillsScreen"),
    "transactions": ("features.transactions.transaction_screen", "TransactionScreen"),
    "notifications": ("features.notifications.notification_screen", "NotificationScreen"),
    "settings": ("screens.settings", "SettingsScreen"),
    "admin_dashboard": ("screens.admin_dashboard", "AdminDashboardScreen"),
    "admin_withdrawals": ("screens.admin_withdrawals", "AdminWithdrawalsScreen"),
    "admin_agents": ("screens.admin_agents", "AdminAgentsScreen"),
    "admin_users": ("screens.admin_users", "AdminUsersScreen"),
    "admin_transactions": ("screens.admin_transactions", "AdminTransactionsScreen"),
    "admin_revenue": ("screens.admin_revenue", "AdminRevenueScreen"),
    "admin_fraud_alerts": ("screens.admin_fraud_alerts", "AdminFraudAlertsScreen"),
}

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
    privacy_mode = BooleanProperty(True)
    is_admin = BooleanProperty(False)
    user_name = StringProperty("Cyber Cash User")
    user_email = StringProperty("support@cybercash.app")
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
    
    # Performance cache for loaded screens
    _screen_cache = {}
    # Debounce for heavy UI tasks
    _theme_task = None

    _warmup_started = False
    _loading_screen_name = ""
    _startup_complete = False
    _startup_attempts = 0
    _startup_request_event = None

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
            # Delay theme toggle to keep UI responsive
            if self._theme_task:
                self._theme_task.cancel()
            self._theme_task = Clock.schedule_once(
                lambda dt: self.theme_manager.toggle(), 0.1)

    def _warm_backend(self) -> None:
        try:
            from api.client import api_client

            api_client.warmup()
        except Exception:
            pass

    def on_start(self) -> None:
        # Kick off startup routing only after the first frame has been scheduled.
        self.request_startup_route()

    def request_startup_route(self, delay: float = 0.20) -> None:
        if self._startup_complete:
            return
        if self._startup_request_event is not None:
            return
        self._startup_request_event = Clock.schedule_once(self._run_startup_route, delay)

    def _run_startup_route(self, *_args) -> None:
        self._startup_request_event = None
        if self._startup_complete:
            return
        if self.complete_startup():
            return

        self._startup_attempts += 1
        if self._startup_attempts < 4:
            retry_delay = min(0.25 * self._startup_attempts + 0.20, 1.0)
        else:
            if self._startup_attempts == 4:
                logging.error("Startup routing still failing after %s attempts.", self._startup_attempts)
            retry_delay = 1.0
        self.request_startup_route(delay=retry_delay)

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
            if screen_name not in self._screen_cache:
                module = import_module(module_name)
                self._screen_cache[screen_name] = getattr(module, class_name)
            
            screen_cls = self._screen_cache[screen_name]
            # Point 1: Fixed race condition. The screen must be added synchronously
            # so that ScreenManager.current can be set immediately in go_to_screen.
            sm.add_widget(screen_cls(name=screen_name))
            return True
        except Exception:
            logging.exception("Failed to load screen %s", screen_name)
            return False
        finally:
            # Clear image cache to free memory on low-end devices
            Cache.remove('kv.image')
            self._loading_screen_name = ""

    def ensure_screens(self, screen_names) -> None:
        for screen_name in screen_names:
            self.ensure_screen(screen_name)

    def go_to_screen(self, screen_name: str, fallback: str = "login") -> bool:
        target = str(screen_name or "").strip()

        # Centralized Role-Based Access Control (RBAC)
        if target.startswith("admin_") and not self.is_admin:
            logging.warning("RBAC Security: Access to restricted screen '%s' denied for non-admin user.", target)
            target = "home" if self.access_token else "login"

        sm = getattr(self, "root", None)
        if sm and self.ensure_screen(target):
            previous = str(getattr(sm, "previous_screen", "") or "").strip()
            if target in {"deposit", "withdraw", "p2p_transfer"}:
                style = "slide_right"
            elif target == previous:
                style = "slide_left"
            elif target == "login":
                style = "fade"
            else:
                style = "fade_up"
            smooth_switch_screen(sm, target, style=style)
            return True
        if sm and fallback and self.ensure_screen(fallback):
            smooth_switch_screen(sm, fallback, style="fade")
            return True
        return False

    def _is_mobile_runtime(self) -> bool:
        return str(platform or "").strip().lower() in {"android", "ios"}

    def on_privacy_mode(self, _instance, value: bool) -> None:
        save_privacy_mode(value)
        self.set_privacy_mode(value)

    def set_privacy_mode(self, enabled: bool) -> None:
        """
        Implementation of 'Privacy Mode' for Android.
        Uses FLAG_SECURE to hide app content in the Task Switcher (Recent Apps)
        and prevents screen recording/screenshots.
        """
        if platform != "android":
            return

        try:
            from jnius import autoclass

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            LayoutParams = autoclass("android.view.WindowManager$LayoutParams")
            activity = PythonActivity.mActivity

            def _apply():
                window = activity.getWindow()
                if enabled:
                    window.addFlags(LayoutParams.FLAG_SECURE)
                else:
                    window.clearFlags(LayoutParams.FLAG_SECURE)

            activity.runOnUiThread(_apply)
        except Exception:
            logging.exception("Failed to apply Android Privacy Mode flags")

    def on_pause(self):
        # Allow the app to pause and save the state
        return True

    def on_resume(self):
        # Trigger App Lock if authenticated and biometric-ready
        if self.access_token:
            data = get_remember_me()
            if data.get("pin"):
                self.request_biometric_auth(
                    reason="Resume Session",
                    on_success=lambda: None, # Stay on current screen
                    on_failure=self._lock_app_to_login
                )

    def _lock_app_to_login(self, message="Session Locked"):
        self.reset_session_state(clear_wallet_state=False)
        self.go_to_screen("login")

    def reset_session_state(self, *, clear_wallet_state: bool = False) -> None:
        self.access_token = ""
        self.pending_momo = ""
        self.user_name = "Cyber Cash User"
        self.is_admin = False
        try:
            session.save("")
            session.set_user(None)
        except Exception:
            clear_token()
        if not clear_wallet_state:
            return

        try:
            self.pending_wallet_action = ""
            self.pending_deposit_amount = ""
            self.pending_deposit_autostart = False
            self.wallet_entry_action = ""
        except Exception:
            pass

    def request_biometric_auth(self, reason="Confirm Identity", on_success=None, on_failure=None):
        """Central biometric service for Login and App Lock."""
        data = get_remember_me()
        momo = data.get("momo", "User")
        pin = data.get("pin")

        if not pin:
            if on_failure: on_failure("Biometric not set up")
            return

        if platform == 'android':
            try:
                from jnius import autoclass, PythonJavaClass, java_method
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                BiometricPrompt = autoclass('androidx.biometric.BiometricPrompt')
                PromptInfo = autoclass('androidx.biometric.BiometricPrompt$PromptInfo')
                ContextCompat = autoclass('androidx.core.content.ContextCompat')
                
                activity = PythonActivity.mActivity
                executor = ContextCompat.getMainExecutor(activity)

                class BiometricCallback(PythonJavaClass):
                    __javainterfaces__ = ['androidx/biometric/BiometricPrompt$AuthenticationCallback']
                    def __init__(self, s_cb, f_cb):
                        self.s_cb = s_cb
                        self.f_cb = f_cb
                        super().__init__()

                    @java_method('(Landroidx/biometric/BiometricPrompt$AuthenticationResult;)V')
                    def onAuthenticationSucceeded(self, result):
                        Clock.schedule_once(lambda dt: self.s_cb())

                    @java_method('(ILjava/lang/CharSequence;)V')
                    def onAuthenticationError(self, errorCode, errString):
                        if int(errorCode) != 13: # 13 is cancel
                            Clock.schedule_once(lambda dt: self.f_cb(str(errString)))

                callback = BiometricCallback(
                    lambda: on_success() if on_success else None,
                    lambda msg: on_failure(msg) if on_failure else None
                )
                prompt = BiometricPrompt(activity, executor, callback)
                builder = PromptInfo.Builder()
                builder.setTitle("CYBER CASH Secure Access")
                builder.setSubtitle(f"{reason} for {momo}")
                builder.setNegativeButtonText("Cancel")
                builder.setAllowedAuthenticators(15)
                activity.runOnUiThread(lambda: prompt.authenticate(builder.build()))
                return
            except Exception:
                logging.warning("Native auth failed")

        # Fallback simulation
        from core.popup_manager import show_message_dialog
        show_message_dialog(
            self.root, title="Biometric Check", 
            message=f"Authenticating {momo}...",
            on_close=lambda: Clock.schedule_once(lambda dt: on_success(), 0.5) if on_success else None
        )

    def _open_authenticated_start_screen(self, *_args) -> None:
        if self.access_token:
            self.go_to_screen("home", fallback="login")

    def complete_startup(self, *_args) -> bool:
        sm = getattr(self, "root", None)
        if not sm:
            return False

        target = "home" if self.access_token else "login"
        if not self.go_to_screen(target, fallback="login"):
            logging.warning("Startup route to %s is not ready yet; retrying.", target)
            return False

        self._startup_complete = True
        self._startup_attempts = 0

        if not self._warmup_started:
            self._warmup_started = True
            Clock.schedule_once(
                lambda _dt: threading.Thread(target=self._warm_backend, daemon=True).start(),
                0.35,
            )
        return True

    def build(self):
        self.theme_cls.theme_style = "Dark"
        register_font_style_aliases(self.theme_cls.font_styles)
        # This KivyMD build errors on "Amber"; the app's gold styling comes from CyberTheme.
        self.theme_cls.primary_palette = "Green"
        self.app_state = AppState()
        self.session_manager = session
        self.event_bus = EventBus()
        self.notification_manager = notification_manager
        self.pending_momo = ""
        snapshot = self.session_manager.restore()
        self.access_token = snapshot.access_token
        self.wallet_entry_action = ""
        self.pending_wallet_action = ""
        self.pending_deposit_amount = ""
        self.pending_deposit_autostart = False
        self.theme_mode = "Dark"
        self.gold = list(CyberTheme.GOLD)
        self.emerald = list(CyberTheme.EMERALD)
        self.dark_bg = list(CyberTheme.DARK_BG)
        self.card_bg = list(CyberTheme.CARD_BG)
        self.success = list(CyberTheme.SUCCESS)
        self.error = list(CyberTheme.ERROR)
        self.btc = list(CyberTheme.BTC)
        self._startup_complete = False
        self._startup_attempts = 0
        self._startup_request_event = None

        # Load and apply initial Privacy Mode state
        self.privacy_mode = snapshot.privacy_mode
        self.set_privacy_mode(self.privacy_mode)

        self.theme_manager = ThemeManager(self)
        self.theme_manager.apply(self.theme_mode, animate=False)

        login_kv = Path(__file__).resolve().parent / "features" / "auth" / "login_screen.kv"
        if login_kv.exists():
            Builder.load_file(str(login_kv))

        sm = AppScreenManager(transition=NoTransition())
        sm.add_widget(SplashScreen(name="splash"))
        sm.current = "splash"

        return sm
