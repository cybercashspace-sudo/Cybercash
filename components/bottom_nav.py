from __future__ import annotations

from core.bottom_nav import BottomNavBar as _BottomNavBar

BottomNavBar = _BottomNavBar
BottomNav = _BottomNavBar


try:
    from kivy.factory import Factory

    Factory.register("BottomNavBar", cls=BottomNavBar)
except Exception:
    pass
