from __future__ import annotations

from screens.home_screen import HomeScreen as _LegacyHomeScreen


class HomeScreen(_LegacyHomeScreen):
    """Compatibility wrapper for the existing dashboard screen."""
