from __future__ import annotations

from kivy.properties import StringProperty
from kivymd.uix.boxlayout import MDBoxLayout


class AuthHeader(MDBoxLayout):
    title = StringProperty("CYBER CASH")
    subtitle = StringProperty("Secure access to your wallet")
    icon = StringProperty("shield-crown")
