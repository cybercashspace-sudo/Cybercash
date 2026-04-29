from __future__ import annotations

import math
import os
import tempfile
import wave
from functools import lru_cache

from kivy.core.audio import SoundLoader


_CLICK_FILENAME = "cyber_cash_click.wav"


def _click_path() -> str:
    base_dir = os.path.join(tempfile.gettempdir(), "cyber_cash_feedback")
    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, _CLICK_FILENAME)


def _write_click_sound(path: str) -> None:
    sample_rate = 22050
    duration_seconds = 0.06
    total_frames = int(sample_rate * duration_seconds)
    amplitude = 0.38

    with wave.open(path, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)

        frames = bytearray()
        for index in range(total_frames):
            progress = index / float(sample_rate)
            envelope = math.exp(-progress * 46.0)
            tone = math.sin(2.0 * math.pi * 1400.0 * progress)
            sample = int(32767 * amplitude * envelope * tone)
            sample = max(-32768, min(32767, sample))
            frames.extend(sample.to_bytes(2, byteorder="little", signed=True))

        wav_file.writeframes(bytes(frames))


@lru_cache(maxsize=1)
def _load_click_sound():
    path = _click_path()
    if not os.path.exists(path):
        try:
            _write_click_sound(path)
        except Exception:
            return None
    try:
        return SoundLoader.load(path)
    except Exception:
        return None


def play_click() -> bool:
    sound = _load_click_sound()
    if not sound:
        return False
    try:
        sound.stop()
    except Exception:
        pass
    try:
        sound.play()
        return True
    except Exception:
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

    try:
        import winsound

        winsound.MessageBeep()
        return True
    except Exception:
        return False


def tap_feedback(*, sound: bool = True, haptic: bool = True) -> None:
    if sound:
        play_click()
    if haptic:
        vibrate()
