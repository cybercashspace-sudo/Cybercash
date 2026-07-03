import sys
import types
import unittest
import logging
from unittest.mock import MagicMock


def install_kivy_stubs():
    def module(name):
        mod = types.ModuleType(name)
        sys.modules[name] = mod
        return mod

    kivy = module("kivy")
    kivy_config = module("kivy.config")
    kivy_clock = module("kivy.clock")
    kivy_props = module("kivy.properties")
    kivy_screenmanager = module("kivy.uix.screenmanager")
    kivy_utils = module("kivy.utils")
    kivy_cache = module("kivy.cache")
    module("kivy.uix")

    class ConfigStub:
        @staticmethod
        def set(*_args, **_kwargs):
            return None

    class ClockStub:
        @staticmethod
        def schedule_once(callback, *_args, **_kwargs):
            callback(0)

    class CacheStub:
        @staticmethod
        def remove(*_args, **_kwargs):
            return None

    class ScreenManagerStub:
        def __init__(self, *_args, **_kwargs):
            self.screens = []
            self.current = ""

        def add_widget(self, widget):
            self.screens.append(widget)

        def has_screen(self, name):
            return any(getattr(screen, "name", "") == name for screen in self.screens)

        def on_current(self, *_args, **_kwargs):
            return None

    class FadeTransitionStub:
        def __init__(self, *_args, **_kwargs):
            pass

    def property_stub(default=None, *_args, **_kwargs):
        return default

    kivy.config = kivy_config
    kivy_config.Config = ConfigStub
    kivy_clock.Clock = ClockStub
    kivy_props.BooleanProperty = property_stub
    kivy_props.ColorProperty = property_stub
    kivy_props.StringProperty = property_stub
    kivy_screenmanager.ScreenManager = ScreenManagerStub
    kivy_screenmanager.FadeTransition = FadeTransitionStub
    kivy_utils.platform = "win"
    kivy_cache.Cache = CacheStub

    kivymd_app = module("kivymd.app")
    module("kivymd")

    class MDAppStub:
        _running_app = None

        def __init__(self, *_args, **_kwargs):
            type(self)._running_app = self
            self.theme_cls = types.SimpleNamespace(font_styles={}, theme_style="", primary_palette="")

        @classmethod
        def get_running_app(cls):
            return cls._running_app

    kivymd_app.MDApp = MDAppStub


def install_project_stubs():
    def module(name):
        mod = types.ModuleType(name)
        sys.modules[name] = mod
        return mod

    silent_touch = module("core.silent_touch")
    silent_touch.install_silent_touch = lambda: None

    kivymd_compat = module("core.kivymd_compat")
    kivymd_compat.install_kivymd_font_style_compat = lambda: None
    kivymd_compat.register_font_style_aliases = lambda *_args, **_kwargs: None

    theme_manager = module("core.theme_manager")
    theme_manager.ThemeManager = MagicMock

    splash = module("screens.splash")

    class SplashScreenStub:
        def __init__(self, name="splash", **_kwargs):
            self.name = name

    splash.SplashScreen = SplashScreenStub

    storage = module("storage")
    storage.get_token = lambda: ""
    storage.get_remember_me = lambda: {}
    storage.save_token = lambda *_args, **_kwargs: None
    storage.get_privacy_mode = lambda: True
    storage.save_privacy_mode = lambda *_args, **_kwargs: None

    theme = module("theme")

    class CyberThemeStub:
        GOLD = [1, 0.8, 0.2, 1]
        EMERALD = [0.1, 0.8, 0.4, 1]
        DARK_BG = [0.03, 0.05, 0.08, 1]
        CARD_BG = [0.08, 0.1, 0.13, 1]
        SUCCESS = [0.3, 0.8, 0.4, 1]
        ERROR = [0.9, 0.2, 0.2, 1]
        BTC = [0.95, 0.55, 0.1, 1]

    theme.CyberTheme = CyberThemeStub


install_kivy_stubs()
install_project_stubs()
logging.disable(logging.CRITICAL)

from kivy_app import CyberCashApp


class TestKivyRBAC(unittest.TestCase):
    def setUp(self):
        self.app = CyberCashApp()
        self.app.root = MagicMock()
        self.app.ensure_screen = MagicMock(return_value=True)
        self.app.access_token = "valid_token"

    def test_admin_screen_access_denied_for_non_admin(self):
        self.app.is_admin = False
        self.app.go_to_screen("admin_dashboard")

        self.app.ensure_screen.assert_called_with("home")
        self.assertEqual(self.app.root.current, "home")

    def test_admin_screen_access_allowed_for_admin(self):
        self.app.is_admin = True
        self.app.go_to_screen("admin_dashboard")

        self.app.ensure_screen.assert_called_with("admin_dashboard")
        self.assertEqual(self.app.root.current, "admin_dashboard")


if __name__ == "__main__":
    unittest.main()
