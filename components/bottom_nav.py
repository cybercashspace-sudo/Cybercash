from kivymd.uix.bottomnavigation import MDBottomNavigation, MDBottomNavigationItem


class BottomNav(MDBottomNavigation):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add_widget(MDBottomNavigationItem(name="home", text="Home", icon="home"))
        self.add_widget(MDBottomNavigationItem(name="wallet", text="Wallet", icon="wallet"))
        self.add_widget(MDBottomNavigationItem(name="cards", text="Cards", icon="credit-card"))
        self.add_widget(MDBottomNavigationItem(name="settings", text="Settings", icon="cog"))


class BottomNavBar(BottomNav):
    """Compatibility alias for the shared bottom navigation component."""


try:
    from kivy.factory import Factory

    Factory.register("BottomNavBar", cls=BottomNavBar)
except Exception:
    pass
