import os
import threading
import logging
from importlib import import_module
from pathlib import Path

from core.bootstrap import ensure_runtime_bootstrap

ensure_runtime_bootstrap(Path(__file__).resolve().parent)

# Performance Tuning for Low-End Devices
from kivy.config import Config
Config.set('graphics', 'max_fps', '40')  # Balance between smoothness and battery
Config.set('graphics', 'multisamples', '0') # Disable anti-aliasing to save GPU cycles

# Android 14+ can emit noisy SDL HID receiver errors while probing gamepads.
os.environ.setdefault("SDL_JOYSTICK_HIDAPI", "0")
os.environ.setdefault("SDL_HINT_JOYSTICK_HIDAPI", "0")

from kivy.clock import Clock
from kivy.properties import BooleanProperty, ColorProperty, StringProperty
from kivy.uix.screenmanager import FadeTransition, ScreenManager
from kivymd.app import MDApp

from kivy.utils import platform

from core.silent_touch import install_silent_touch
from core.config import config as app_config
from core.logger import get_logger
from core.session import session
from core.event_bus import EventBus
from core.navigation import navigate

install_silent_touch()

from core.kivymd_compat import (
    install_kivymd_font_style_compat,
    register_font_style_aliases,
)
from core.theme_manager import ThemeManager
from core.app_state import AppState
from core.network import NetworkManager
from features.home.home_controller import HomeController
from features.notifications.notification_controller import NotificationController
from api.client import FAST_TIMEOUT, api_client

install_kivymd_font_style_compat()

logger = get_logger("cybercash.app")
BIOMETRIC_STRONG_AUTHENTICATOR = 0x000F


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

from screens.splash_screen import SplashScreen
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
    "home": ("screens.dashboard", "DashboardScreen"),
    "wallet": ("screens.wallet", "WalletScreen"),
    "deposit": ("screens.wallet", "DepositScreen"),
    "withdraw": ("screens.wallet", "WithdrawScreen"),
    # Keep the service screens aligned with the versions packaged in the reference APK.
    # The bundle screen also handles the authenticated live catalog and agent entry path.
    "airtime": ("screens.airtime", "AirtimeScreen"),
    "data_bundle": ("screens.data_bundle", "DataBundleScreen"),
    "p2p_transfer": ("screens.p2p_transfer", "P2PTransferScreen"),
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
    "profile": ("screens.profile", "ProfileScreen"),
    "settings": ("screens.settings", "SettingsScreen"),
    "agent_dashboard": ("features.agent.agent_dashboard", "AgentDashboard"),
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

    def __init__(self, **kwargs):
        kwargs.setdefault("transition", FadeTransition(duration=0.12))
        super().__init__(**kwargs)

    def has_screen(self, name):
        if super().has_screen(name):
            return True
        app = MDApp.get_running_app()
        ensure_screen = getattr(app, "ensure_screen", None)
        return bool(ensure_screen and ensure_screen(str(name or "")))

    def on_current(self, _instance, value):
        previous = self._last_screen
        super().on_current(_instance, value)
        current = str(value or "")
        if previous and previous != current:
            self.previous_screen = previous
            logger.info("Navigation: %s -> %s", previous, current)
        elif current:
            logger.info("Navigation: %s", current)
        app = MDApp.get_running_app()
        app_state = getattr(app, "app_state", None) if app else None
        if isinstance(app_state, AppState):
            app_state.set_screen(current, previous)
        self._last_screen = current


RootScreenManager = AppScreenManager


class CyberCashApp(MDApp):
    theme_mode = StringProperty("Dark")
    privacy_mode = BooleanProperty(True)
    is_admin = BooleanProperty(False)
    is_agent_active = BooleanProperty(False)
    user_role = StringProperty("user")
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

    def request_startup_route(self, delay: float | None = None) -> None:
        if self._startup_complete:
            return
        if self._startup_request_event is not None:
            return
        startup_delay = (
            float(app_config.startup_splash_seconds)
            if delay is None
            else float(delay)
        )
        self._startup_request_event = Clock.schedule_once(self._run_startup_route, startup_delay)

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
            logger.exception("Failed to load screen %s", screen_name)
            return False
        finally:
            # Clear image cache to free memory on low-end devices
            Cache.remove('kv.image')
            self._loading_screen_name = ""

    def ensure_screens(self, screen_names) -> None:
        for screen_name in screen_names:
            self.ensure_screen(screen_name)

    def go_to_screen(
        self,
        screen_name: str,
        fallback: str = "login",
        transition_style: str | None = None,
    ) -> bool:
        target = str(screen_name or "").strip()
        if not target:
            return False
        self._admin_dashboard_entry_authorized = False

        # Centralized Role-Based Access Control (RBAC)
        if target.startswith("admin_") and not self._is_admin_account():
            logger.warning("RBAC Security: Access to restricted screen '%s' denied for non-admin user.", target)
            target = "home" if self.access_token else "login"

        sm = getattr(self, "root", None)
        current = str(getattr(sm, "current", "") or "").strip() if sm is not None else ""
        if target == "admin_dashboard" and current != "home":
            logger.warning("RBAC Security: Admin dashboard can only be opened from the user dashboard.")
            target = "home" if self.access_token else "login"

        if sm is not None:
            if current == target:
                return True
            if getattr(sm, "_cybercash_nav_busy", False):
                pending = str(getattr(sm, "_cybercash_pending_target", "") or "").strip()
                return pending == target

        if sm and self.ensure_screen(target):
            if target == "admin_dashboard":
                self._admin_dashboard_entry_authorized = True
            previous = str(getattr(sm, "previous_screen", "") or "").strip()
            routed = navigate(
                sm,
                target,
                previous=previous,
                fallback=fallback,
                transition_style=transition_style,
            )
            if not routed:
                self._admin_dashboard_entry_authorized = False
            return routed
        if sm and fallback and self.ensure_screen(fallback):
            previous = str(getattr(sm, "previous_screen", "") or "").strip()
            return navigate(sm, fallback, previous=previous, fallback="", transition_style="fade")
        logger.warning("Navigation failed: target=%s fallback=%s", target, fallback)
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
        # Ignore the pause caused by the Android biometric sheet itself.
        if not getattr(self, "_biometric_prompt_active", False):
            self._biometric_unlocked_for_session = False
        return True

    def on_resume(self):
        if not getattr(self, "_startup_complete", False) or not self.access_token:
            return
        if self._biometric_opted_in() and not getattr(self, "_biometric_unlocked_for_session", False):
            manager = getattr(self, "root", None)
            resume_target = str(getattr(manager, "current", "") or self.get_authenticated_target())
            if resume_target in {"login", "splash"}:
                resume_target = self.get_authenticated_target()
            self.go_to_screen("login", fallback="login")
            self.request_biometric_auth(
                reason="Unlock your session",
                on_success=lambda: self.go_to_screen(resume_target, fallback="login"),
                on_failure=self._lock_app_to_login,
            )

    def _biometric_opted_in(self) -> bool:
        try:
            return bool(get_remember_me().get("biometric_enabled", False))
        except Exception:
            return False

    def is_biometric_available(self) -> bool:
        """Return whether Android has an enrolled strong biometric for this device."""
        if platform != "android":
            return False
        try:
            from jnius import autoclass

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            BiometricManager = autoclass("androidx.biometric.BiometricManager")
            availability = BiometricManager.from_(PythonActivity.mActivity).canAuthenticate(
                BIOMETRIC_STRONG_AUTHENTICATOR
            )
            return int(availability) == 0  # BIOMETRIC_SUCCESS for BIOMETRIC_STRONG.
        except Exception:
            logger.debug("Could not check Android biometric availability", exc_info=True)
            return False

    def _lock_app_to_login(self, message="Session Locked"):
        self._biometric_unlocked_for_session = False
        try:
            remembered = get_remember_me()
            if remembered.get("momo"):
                session.set_remember_me(
                    remembered.get("momo", ""),
                    first_name=remembered.get("first_name", ""),
                    biometric_enabled=False,
                )
        except Exception:
            logging.exception("Could not disable biometric unlock after a failed prompt")
        self.reset_session_state(clear_wallet_state=False)
        self.go_to_screen("login")
        if message:
            show_app_snackbar("Biometric unlock was cancelled or unavailable. Sign in with your PIN; you can enable it again after login.")

    def reset_session_state(self, *, clear_wallet_state: bool = False) -> None:
        self.stop_background_services()
        self._admin_dashboard_entry_authorized = False
        self._last_connectivity_state = None
        self.access_token = ""
        self.pending_momo = ""
        self.user_name = "Cyber Cash User"
        self.is_admin = False
        self.is_agent_active = False
        self.user_role = "user"
        try:
            session.clear_auth()
        except Exception:
            clear_token()
        try:
            notification_manager.clear()
        except Exception:
            pass
        app_state = getattr(self, "app_state", None)
        if isinstance(app_state, AppState):
            app_state.reset()
        dashboard_controller = getattr(self, "dashboard_controller", None)
        if dashboard_controller is not None:
            try:
                dashboard_controller.state.reset()
            except Exception:
                pass
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
        """Require the Android system biometric prompt for an existing session."""
        if getattr(self, "_biometric_prompt_active", False):
            return False
        if not self.access_token or not session.authenticated():
            if on_failure:
                on_failure("Sign in with your PIN before using biometric unlock.")
            return False
        if not self._biometric_opted_in():
            if on_failure:
                on_failure("Biometric unlock is not enabled for this device.")
            return False
        if platform != "android":
            if on_failure:
                on_failure("Biometric unlock is available in the Android app.")
            return False

        self._biometric_prompt_active = True
        self._biometric_unlocked_for_session = False
        request_id = int(getattr(self, "_biometric_request_id", 0)) + 1
        self._biometric_request_id = request_id
        settled = {"value": False}

        def finish(success, message=""):
            if settled["value"]:
                return
            settled["value"] = True

            def apply_result(_dt):
                if request_id != getattr(self, "_biometric_request_id", 0):
                    return
                self._biometric_prompt_active = False
                self._biometric_prompt = None
                self._biometric_callback = None
                if success:
                    self._biometric_unlocked_for_session = True
                    if on_success:
                        on_success()
                elif on_failure:
                    on_failure(str(message or "Biometric check was not completed."))

            Clock.schedule_once(apply_result, 0)

        try:
            from jnius import autoclass, PythonJavaClass, java_method

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            BiometricPrompt = autoclass("androidx.biometric.BiometricPrompt")
            PromptInfo = autoclass("androidx.biometric.BiometricPrompt$PromptInfo")
            BiometricManager = autoclass("androidx.biometric.BiometricManager")
            ContextCompat = autoclass("androidx.core.content.ContextCompat")
            activity = PythonActivity.mActivity
            authenticators = BIOMETRIC_STRONG_AUTHENTICATOR  # Secure fingerprint or face.
            availability = BiometricManager.from_(activity).canAuthenticate(authenticators)
            if int(availability) != 0:
                finish(False, "Set up a secure fingerprint or face unlock on this device, then sign in with your PIN.")
                return False
            executor = ContextCompat.getMainExecutor(activity)

            class BiometricCallback(PythonJavaClass):
                __javainterfaces__ = ["androidx/biometric/BiometricPrompt$AuthenticationCallback"]
                __javacontext__ = "app"

                @java_method("(Landroidx/biometric/BiometricPrompt$AuthenticationResult;)V")
                def onAuthenticationSucceeded(self, _result):
                    finish(True)

                @java_method("(ILjava/lang/CharSequence;)V")
                def onAuthenticationError(self, _error_code, error_text):
                    finish(False, str(error_text or "Biometric check was not completed."))

                @java_method("()V")
                def onAuthenticationFailed(self):
                    # A failed sample leaves the system sheet open for another try.
                    return

            callback = BiometricCallback()
            prompt = BiometricPrompt(activity, executor, callback)
            builder = PromptInfo.Builder()
            builder.setTitle("CYBER CASH Secure Access")
            builder.setSubtitle(str(reason or "Unlock your session"))
            builder.setNegativeButtonText("Use PIN later")
            builder.setAllowedAuthenticators(authenticators)
            self._biometric_callback = callback
            self._biometric_prompt = prompt
            activity.runOnUiThread(lambda: prompt.authenticate(builder.build()))
            return True
        except Exception:
            logging.exception("Android biometric prompt could not be started")
            finish(False, "Biometric unlock is unavailable right now. Sign in with your PIN.")
            return False

    def _open_authenticated_start_screen(self, *_args) -> None:
        if self.access_token:
            self.go_to_screen(self.get_authenticated_target(), fallback="login")

    def get_authenticated_target(self) -> str:
        if self._is_admin_account():
            return "home"
        role = str(getattr(self, "user_role", "") or "").strip().lower()
        if bool(getattr(self, "is_agent_active", False)) or role == "agent":
            return "agent_dashboard"
        return "home"

    def _is_admin_account(self) -> bool:
        role = str(getattr(self, "user_role", "") or "").strip().lower()
        return bool(getattr(self, "is_admin", False)) or role in {"admin", "super_admin"}

    def consume_admin_dashboard_entry(self) -> bool:
        authorized = bool(getattr(self, "_admin_dashboard_entry_authorized", False))
        self._admin_dashboard_entry_authorized = False
        return authorized and self._is_admin_account()

    def complete_startup(self, *_args) -> bool:
        sm = getattr(self, "root", None)
        if not sm:
            return False

        target = self.get_authenticated_target() if self.access_token else "login"
        biometric_required = bool(self.access_token and self._biometric_opted_in())
        initial_target = "login" if biometric_required else target
        if not self.go_to_screen(initial_target, fallback="login"):
            logger.warning("Startup route to %s is not ready yet; retrying.", initial_target)
            return False

        self._startup_complete = True
        self._startup_attempts = 0

        if not self._warmup_started:
            self._warmup_started = True
            Clock.schedule_once(
                lambda _dt: threading.Thread(target=self._warm_backend, daemon=True).start(),
                0.35,
            )

        if biometric_required:
            def open_after_biometric():
                if self.go_to_screen(target, fallback="login"):
                    self.start_background_services()
                else:
                    self._lock_app_to_login("Please sign in with your PIN to continue.")

            self.request_biometric_auth(
                reason="Unlock your account",
                on_success=open_after_biometric,
                on_failure=self._lock_app_to_login,
            )
            return True

        if self.access_token:
            self.start_background_services()
        return True

    def _ensure_background_runtime(self) -> None:
        if not hasattr(self, "_background_events"):
            self._background_events = {}
        if not hasattr(self, "_background_busy"):
            self._background_busy = set()
        if not hasattr(self, "_background_lock"):
            self._background_lock = threading.RLock()
        if not hasattr(self, "_last_connectivity_state"):
            self._last_connectivity_state = None
        if not hasattr(self, "network_manager"):
            self.network_manager = NetworkManager()
        if not hasattr(self, "notification_controller"):
            self.notification_controller = NotificationController()

    def _bind_global_event_handlers(self) -> None:
        if getattr(self, "_global_event_handlers_bound", False):
            return
        bus = getattr(self, "event_bus", None)
        subscribe = getattr(bus, "subscribe", None)
        if not callable(subscribe):
            return
        subscribe("WalletUpdated", self._handle_wallet_event)
        subscribe("TransactionCreated", self._handle_transaction_event)
        subscribe("NotificationCreated", self._handle_notification_event)
        subscribe("NotificationsUpdated", self._handle_notifications_event)
        self._global_event_handlers_bound = True

    def _merge_dashboard_event(self, event_name: str, payload=None) -> None:
        controller = getattr(self, "dashboard_controller", None)
        if controller is None:
            return
        app_state = getattr(self, "app_state", None)
        if isinstance(app_state, AppState):
            try:
                snapshot = dict(getattr(app_state, "dashboard", {}) or {})
                if snapshot:
                    controller.state.apply(
                        snapshot,
                        source=snapshot.get("source"),
                        online=snapshot.get("online"),
                        loading=snapshot.get("loading"),
                    )
            except Exception:
                pass
        try:
            controller.merge_event_update(event_name, payload)
        except Exception:
            logger.exception("Failed to merge dashboard event: %s", event_name)

    def _handle_wallet_event(self, payload=None) -> None:
        self._merge_dashboard_event("WalletUpdated", payload)

    def _handle_transaction_event(self, payload=None) -> None:
        self._merge_dashboard_event("TransactionCreated", payload)

    def _handle_notification_event(self, payload=None) -> None:
        self._merge_dashboard_event("NotificationCreated", payload)

    def _handle_notifications_event(self, payload=None) -> None:
        self._merge_dashboard_event("NotificationsUpdated", payload)

    def _cancel_background_service(self, name: str) -> None:
        event = getattr(self, "_background_events", {}).pop(name, None)
        if event is not None:
            try:
                event.cancel()
            except Exception:
                pass

    def stop_background_services(self) -> None:
        self._ensure_background_runtime()
        for name in list(getattr(self, "_background_events", {}).keys()):
            self._cancel_background_service(name)
        with self._background_lock:
            self._background_busy.clear()

    def _schedule_background_service(self, name: str, worker, *, interval: float, initial_delay: float = 0.0) -> None:
        self._ensure_background_runtime()
        self._cancel_background_service(name)

        def launch(*_args):
            if not str(getattr(self, "access_token", "") or "").strip():
                return
            with self._background_lock:
                if name in self._background_busy:
                    return
                self._background_busy.add(name)

            def _run():
                try:
                    worker()
                except Exception:
                    logger.exception("Background task failed: %s", name)
                finally:
                    with self._background_lock:
                        self._background_busy.discard(name)

            threading.Thread(target=_run, daemon=True).start()

        if initial_delay >= 0:
            Clock.schedule_once(lambda _dt: launch(), initial_delay)
        self._background_events[name] = Clock.schedule_interval(lambda _dt: launch(), interval)

    def start_background_services(self) -> None:
        self._ensure_background_runtime()
        if not str(getattr(self, "access_token", "") or "").strip():
            return
        self._schedule_background_service("connectivity", self._probe_connectivity_worker, interval=45.0, initial_delay=5.0)
        self._schedule_background_service("notifications", self._sync_notifications_worker, interval=60.0, initial_delay=10.0)
        self._schedule_background_service("session", self._refresh_session_worker, interval=300.0, initial_delay=20.0)

    def _apply_connectivity_state(self, online: bool, error: str = "") -> None:
        self._ensure_background_runtime()
        previous = self._last_connectivity_state
        self._last_connectivity_state = bool(online)
        self.app_state.set_online(online)
        if previous is None or previous == bool(online):
            return
        if online:
            logger.info("Connectivity restored")
        else:
            logger.warning("Network Timeout")
        try:
            self.event_bus.publish("ConnectivityChanged", {"online": bool(online), "error": str(error or "")})
        except Exception:
            pass

    def _probe_connectivity_worker(self) -> None:
        self._ensure_background_runtime()
        online = False
        error = ""
        try:
            online = bool(self.network_manager.probe())
            error = str(self.network_manager.last_error or "")
        except Exception as exc:
            online = False
            error = str(exc or "")
        Clock.schedule_once(lambda _dt, o=online, e=error: self._apply_connectivity_state(o, e))

    def _sync_notifications_worker(self) -> None:
        self._ensure_background_runtime()
        if not str(getattr(self, "access_token", "") or "").strip():
            return
        try:
            items = self.notification_controller.load_notifications()
        except Exception as exc:
            logger.warning("Notification sync failed: %s", exc)
            try:
                items = self.notification_controller.load_cached_notifications()
            except Exception:
                items = []
        Clock.schedule_once(lambda _dt, rows=items: self._apply_notification_sync(rows))

    def _apply_notification_sync(self, rows) -> None:
        items = [item for item in (rows or []) if isinstance(item, dict)]
        self.notification_manager.update(items)
        try:
            self.app_state.set_notifications(items)
        except Exception:
            pass
        try:
            self.event_bus.publish("NotificationsUpdated", items)
        except Exception:
            pass

    def _refresh_session_worker(self) -> None:
        token = str(getattr(self, "access_token", "") or "").strip()
        if not token:
            return
        try:
            result = api_client.request(
                "GET",
                "/auth/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=FAST_TIMEOUT,
                failover=False,
            )
        except Exception:
            logger.warning("Wallet Refresh Failed")
            return

        status_code = int(result.get("status_code", 0) or 0)
        data = result.get("data", {})
        if status_code in {401, 403}:
            Clock.schedule_once(lambda _dt: self._handle_expired_session())
            return
        if isinstance(data, dict):
            Clock.schedule_once(lambda _dt, payload=data: self._apply_session_refresh(payload))

    def _apply_session_refresh(self, payload: dict) -> None:
        if not isinstance(payload, dict):
            return
        user_payload = dict(payload or {})
        name = str(
            user_payload.get("name")
            or user_payload.get("full_name")
            or user_payload.get("first_name")
            or self.user_name
            or ""
        ).strip()
        if name:
            self.user_name = name
        try:
            self.app_state.set_user(user_payload)
        except Exception:
            pass
        session_manager = getattr(self, "session_manager", None)
        if session_manager is not None:
            try:
                session_manager.set_user(user_payload)
            except Exception:
                pass

    def _handle_expired_session(self) -> None:
        logger.warning("Wallet Refresh Failed")
        self.reset_session_state(clear_wallet_state=False)
        self.go_to_screen("login")

    def build(self):
        self.theme_cls.theme_style = "Dark"
        register_font_style_aliases(self.theme_cls.font_styles)
        # This KivyMD build errors on "Amber"; the app's gold styling comes from CyberTheme.
        self.theme_cls.primary_palette = "Green"
        self.app_state = AppState()
        self.session_manager = session
        self.event_bus = EventBus()
        self.dashboard_controller = HomeController()
        self.notification_manager = notification_manager
        self.pending_momo = ""
        snapshot = self.session_manager.restore()
        self.access_token = snapshot.access_token
        self.wallet_entry_action = ""
        self.pending_wallet_action = ""
        self.pending_deposit_amount = ""
        self.pending_deposit_autostart = False
        self._background_events = {}
        self._background_busy = set()
        self._background_lock = threading.RLock()
        self._last_connectivity_state = None
        self.network_manager = NetworkManager()
        self.notification_controller = NotificationController()
        self._global_event_handlers_bound = False
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
        self._biometric_prompt_active = False
        self._biometric_prompt = None
        self._biometric_callback = None
        self._biometric_request_id = 0
        self._biometric_unlocked_for_session = False
        self._admin_dashboard_entry_authorized = False
        self.app_state.set_screen("splash", "")

        # Load and apply initial Privacy Mode state
        self.privacy_mode = snapshot.privacy_mode
        snapshot_user = snapshot.user if isinstance(snapshot.user, dict) else {}
        if snapshot_user:
            snapshot_role = str(snapshot_user.get("role") or "").strip().lower()
            snapshot_is_admin = bool(snapshot_user.get("is_admin") or snapshot_role in {"admin", "super_admin"})
            snapshot_is_agent = bool(
                snapshot_user.get("is_agent")
                or snapshot_user.get("agent_active")
                or snapshot_role == "agent"
            )
            try:
                self.app_state.set_user(snapshot_user)
            except Exception:
                pass
            self.user_name = str(
                snapshot_user.get("name")
                or snapshot_user.get("full_name")
                or snapshot_user.get("first_name")
                or self.user_name
                or ""
            ).strip() or self.user_name
            self.is_admin = snapshot_is_admin
            self.is_agent_active = snapshot_is_agent
            self.user_role = snapshot_role or ("admin" if snapshot_is_admin else "agent" if snapshot_is_agent else "user")
        self.set_privacy_mode(self.privacy_mode)

        self.theme_manager = ThemeManager(self)
        self.theme_manager.apply(self.theme_mode, animate=False)
        self._bind_global_event_handlers()

        sm = AppScreenManager()
        sm.add_widget(SplashScreen(name="splash"))
        sm.current = "splash"

        return sm
