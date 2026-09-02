from __future__ import annotations

from kivy.clock import Clock
from kivy.uix.screenmanager import FadeTransition, NoTransition, SlideTransition

DEFAULT_TRANSITION_DURATION = 0.12


def _default_transition(duration: float = DEFAULT_TRANSITION_DURATION):
    return FadeTransition(duration=max(0.10, float(duration or DEFAULT_TRANSITION_DURATION)))


def _build_transition(style: str, duration: float):
    style = str(style or "").strip().lower()
    duration = max(0.10, float(duration or DEFAULT_TRANSITION_DURATION))

    if style == "none":
        return NoTransition()
    if style == "slide_right":
        return SlideTransition(direction="right", duration=min(duration, 0.14))
    if style == "slide_left":
        return SlideTransition(direction="left", duration=min(duration, 0.14))
    if style in {"fade", "fade_up"}:
        return FadeTransition(duration=duration)
    return FadeTransition(duration=duration)


def _cancel_restore_event(manager) -> None:
    event = getattr(manager, "_cybercash_restore_event", None)
    if event is None:
        return
    try:
        event.cancel()
    except Exception:
        pass
    finally:
        manager._cybercash_restore_event = None


def smooth_switch_screen(manager, target: str, *, duration: float = 0.18, style: str = "fade_up") -> bool:
    """Switch screens with built-in Kivy transitions and a short lock.

    The helper intentionally avoids manual widget animations. That keeps the
    implementation light on low-end phones and prevents callback buildup when
    users tap navigation controls repeatedly.
    """

    if manager is None:
        return False

    target = str(target or "").strip()
    if not target:
        return False

    current = getattr(manager, "current_screen", None)
    if current is None:
        try:
            manager.current = target
        except Exception:
            return False
        return True

    if str(getattr(current, "name", "") or "") == target:
        return True

    if getattr(manager, "_cybercash_nav_busy", False):
        pending = str(getattr(manager, "_cybercash_pending_target", "") or "").strip()
        return pending == target

    try:
        manager.get_screen(target)
    except Exception:
        try:
            manager.current = target
        except Exception:
            return False
        return True

    _cancel_restore_event(manager)
    manager._cybercash_nav_busy = True
    manager._cybercash_pending_target = target
    manager.transition = _build_transition(style, duration)

    try:
        manager.current = target
    except Exception:
        manager._cybercash_nav_busy = False
        manager._cybercash_pending_target = ""
        manager.transition = _default_transition(duration)
        return False

    def _restore_default(_dt):
        manager._cybercash_nav_busy = False
        manager._cybercash_pending_target = ""
        manager.transition = _default_transition(duration)
        manager._cybercash_restore_event = None

    manager._cybercash_restore_event = Clock.schedule_once(_restore_default, duration + 0.03)
    return True
