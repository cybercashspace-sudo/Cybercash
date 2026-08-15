from __future__ import annotations

from kivy.animation import Animation
from kivy.clock import Clock


def smooth_switch_screen(manager, target: str, *, duration: float = 0.25, style: str = "fade_up") -> bool:
    """Switch screens with a lightweight Kivy animation."""

    if manager is None:
        return False

    target = str(target or "").strip()
    if not target:
        return False

    current = getattr(manager, "current_screen", None)
    if current is None:
        manager.current = target
        return True
    if getattr(current, "name", "") == target:
        return True

    try:
        target_screen = manager.get_screen(target)
    except Exception:
        manager.current = target
        return True

    if style == "none":
        manager.current = target
        target_screen.opacity = 1
        return True

    def _complete(*_args):
        manager.current = target
        target_screen.opacity = 0
        if style == "slide_right":
            target_screen.x = manager.width
            Animation(x=0, opacity=1, duration=duration, transition="out_cubic").start(target_screen)
        elif style == "slide_left":
            target_screen.x = -manager.width
            Animation(x=0, opacity=1, duration=duration, transition="out_cubic").start(target_screen)
        elif style == "fade":
            Animation(opacity=1, duration=duration, transition="out_quad").start(target_screen)
        else:
            target_screen.y = target_screen.y - 18
            Animation(y=0, opacity=1, duration=duration, transition="out_cubic").start(target_screen)

    if style == "slide_right":
        Animation(x=-float(manager.width or 0) * 0.08, opacity=0, duration=duration, transition="out_cubic").start(current)
    elif style == "slide_left":
        Animation(x=float(manager.width or 0) * 0.08, opacity=0, duration=duration, transition="out_cubic").start(current)
    elif style == "fade":
        Animation(opacity=0, duration=duration, transition="out_quad").start(current)
    else:
        Animation(y=getattr(current, "y", 0) + 18, opacity=0, duration=duration, transition="out_cubic").start(current)

    Clock.schedule_once(_complete, duration)
    return True
