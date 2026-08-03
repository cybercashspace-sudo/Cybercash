from __future__ import annotations

import importlib
import sys
import types
import unittest


def _install_stubs(mode_options):
    def module(name):
        mod = types.ModuleType(name)
        sys.modules[name] = mod
        return mod

    for prefix in ("kivy", "kivymd", "core.kivymd_compat"):
        for name in [key for key in list(sys.modules) if key == prefix or key.startswith(f"{prefix}.")]:
            sys.modules.pop(name, None)

    kivy = module("kivy")
    kivy.__path__ = []
    kivy_clock = module("kivy.clock")
    kivy_factory = module("kivy.factory")
    kivy_props = module("kivy.properties")
    kivy_uix = module("kivy.uix")
    kivy_uix.__path__ = []
    module("kivy.uix.screenmanager")

    class ClockStub:
        @staticmethod
        def schedule_once(callback, *_args, **_kwargs):
            return callback(0)

    class FactoryStub:
        classes = {}

        @staticmethod
        def register(name, cls=None):
            FactoryStub.classes[name] = cls

    class ModePropertyStub:
        def __init__(self, options):
            self.options = tuple(options)

        def __get__(self, instance, owner):
            return self

        def __set__(self, instance, value):
            if value not in self.options:
                raise ValueError(f"Invalid mode: {value}")
            instance.assigned_mode = value

    def property_stub(default=None, *_args, **_kwargs):
        return default

    kivy_clock.Clock = ClockStub
    kivy_factory.Factory = FactoryStub
    kivy_props.ColorProperty = property_stub
    kivy_props.OptionProperty = property_stub
    kivy_props.StringProperty = property_stub

    kivymd = module("kivymd")
    kivymd.__path__ = []
    kivymd_uix = module("kivymd.uix")
    kivymd_uix.__path__ = []
    button_module = module("kivymd.uix.button")
    textfield_module = module("kivymd.uix.textfield")

    class MDButton:
        pass

    class MDButtonIcon:
        pass

    class MDButtonText:
        pass

    class MDTextField:
        mode = ModePropertyStub(mode_options)

        def __init__(self):
            self.assigned_mode = None

        def on_mode(self, _instance, value):
            self.assigned_mode = value
            return value

    button_module.MDButton = MDButton
    button_module.MDButtonIcon = MDButtonIcon
    button_module.MDButtonText = MDButtonText
    textfield_module.MDTextField = MDTextField
    kivy.clock = kivy_clock
    kivy.factory = kivy_factory
    kivy.properties = kivy_props
    kivy.uix = kivy_uix
    kivymd.uix = kivymd_uix
    kivymd_uix.button = button_module
    kivymd_uix.textfield = textfield_module

    return textfield_module.MDTextField


class TestKivymdCompat(unittest.TestCase):
    def test_rectangle_mode_stays_rectangle_on_current_kivymd_build(self):
        mdtextfield_cls = _install_stubs(("rectangle", "round", "fill", "line"))

        compat = importlib.import_module("core.kivymd_compat")
        importlib.reload(compat)

        field = mdtextfield_cls()
        field.on_mode(None, "rectangle")

        self.assertEqual(field.assigned_mode, "rectangle")
        self.assertEqual(
            tuple(mdtextfield_cls.mode.options),
            ("rectangle", "round", "fill", "line"),
        )


if __name__ == "__main__":
    unittest.main()
