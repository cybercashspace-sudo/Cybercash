import unittest
from unittest.mock import MagicMock, patch
import sys

# Mock Kivy and KivyMD modules before importing CyberCashApp
sys.modules['kivy'] = MagicMock()
sys.modules['kivy.app'] = MagicMock()
sys.modules['kivy.config'] = MagicMock()
sys.modules['kivy.clock'] = MagicMock()
sys.modules['kivy.properties'] = MagicMock()
sys.modules['kivy.uix'] = MagicMock()
sys.modules['kivy.uix.screenmanager'] = MagicMock()
sys.modules['kivy.utils'] = MagicMock()
sys.modules['kivy.cache'] = MagicMock()
sys.modules['kivymd'] = MagicMock()
sys.modules['kivymd.app'] = MagicMock()

# Mock project internal dependencies
sys.modules['core.silent_touch'] = MagicMock()
sys.modules['core.kivymd_compat'] = MagicMock()
sys.modules['core.theme_manager'] = MagicMock()
sys.modules['screens.splash'] = MagicMock()
sys.modules['storage'] = MagicMock()
sys.modules['theme'] = MagicMock()

from kivy_app import CyberCashApp

class TestKivyRBAC(unittest.TestCase):
    def setUp(self):
        # Initialize app with mocked root (ScreenManager)
        self.app = CyberCashApp()
        self.app.root = MagicMock()
        # Mock ensure_screen to return True (simulating successful screen load)
        self.app.ensure_screen = MagicMock(return_value=True)
        self.app.access_token = "valid_token"

    def test_admin_screen_access_denied_for_non_admin(self):
        """Verify that non-admin users are redirected when accessing admin screens."""
        self.app.is_admin = False
        self.app.go_to_screen("admin_dashboard")
        
        # Should redirect to home for authenticated user
        self.app.ensure_screen.assert_called_with("home")
        self.assertEqual(self.app.root.current, "home")

    def test_admin_screen_access_allowed_for_admin(self):
        """Verify that admin users can access admin screens."""
        self.app.is_admin = True
        self.app.go_to_screen("admin_dashboard")
        
        # Should allow admin_dashboard access
        self.app.ensure_screen.assert_called_with("admin_dashboard")
        self.assertEqual(self.app.root.current, "admin_dashboard")