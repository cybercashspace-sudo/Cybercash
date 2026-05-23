from __future__ import annotations

from typing import Any

_INSTALLED = False


def _disable_view_tree_sounds(view: Any) -> None:
    if view is None:
        return

    try:
        view.setSoundEffectsEnabled(False)
    except Exception:
        pass

    try:
        child_count = int(view.getChildCount())
    except Exception:
        return

    for index in range(child_count):
        try:
            _disable_view_tree_sounds(view.getChildAt(index))
        except Exception:
            pass


def _disable_android_touch_sounds() -> None:
    try:
        from kivy.utils import platform
    except Exception:
        return

    if platform != "android":
        return

    try:
        from android.runnable import run_on_ui_thread
        from jnius import autoclass
    except Exception:
        return

    @run_on_ui_thread
    def _apply() -> None:
        try:
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            decor_view = activity.getWindow().getDecorView()
            _disable_view_tree_sounds(decor_view)

            android_ids = autoclass("android.R$id")
            content_view = activity.findViewById(android_ids.content)
            _disable_view_tree_sounds(content_view)
        except Exception:
            pass

    _apply()


def _mute_kivy_button_sound_hooks() -> None:
    try:
        from kivy.uix.behaviors import ButtonBehavior
    except Exception:
        return

    if hasattr(ButtonBehavior, "sound"):
        try:
            ButtonBehavior.sound = None
        except Exception:
            pass


def install_silent_touch() -> None:
    global _INSTALLED

    if _INSTALLED:
        return
    _INSTALLED = True

    _mute_kivy_button_sound_hooks()
    _disable_android_touch_sounds()

    try:
        from kivy.clock import Clock
    except Exception:
        return

    for delay in (0, 0.25, 1.0, 2.0):
        Clock.schedule_once(lambda _dt: _disable_android_touch_sounds(), delay)
