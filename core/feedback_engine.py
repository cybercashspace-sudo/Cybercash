from __future__ import annotations


def play_click() -> bool:
    return False


def vibrate(duration_ms: int = 50) -> bool:
    try:
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Context = autoclass("android.content.Context")
        vibrator = PythonActivity.mActivity.getSystemService(Context.VIBRATOR_SERVICE)
        if vibrator is None:
            return False
        try:
            if hasattr(vibrator, "hasVibrator") and not vibrator.hasVibrator():
                return False
        except Exception:
            pass
        try:
            vibrator.vibrate(duration_ms)
        except TypeError:
            vibrator.vibrate(int(duration_ms))
        return True
    except Exception:
        pass

    return False


def tap_feedback(*, sound: bool = True, haptic: bool = True) -> None:
    _ = sound
    if haptic:
        vibrate()
