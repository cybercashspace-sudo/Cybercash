from __future__ import annotations

from components.transitions import smooth_switch_screen


def resolve_transition_style(target: str, previous: str = "") -> str:
    target = str(target or "").strip()
    previous = str(previous or "").strip()
    if target in {"deposit", "withdraw", "p2p_transfer"}:
        return "slide_right"
    if target == previous:
        return "slide_left"
    if target == "login":
        return "fade"
    return "fade_up"


def navigate(manager, target: str, previous: str = "", *, fallback: str = "login") -> bool:
    style = resolve_transition_style(target, previous)
    if smooth_switch_screen(manager, target, style=style):
        return True
    if fallback:
        return smooth_switch_screen(manager, fallback, style="fade")
    return False

