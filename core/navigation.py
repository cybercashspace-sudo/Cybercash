from __future__ import annotations

from components.transitions import smooth_switch_screen


def resolve_transition_style(target: str, previous: str = "") -> str:
    target = str(target or "").strip()
    if target in {"deposit", "withdraw", "p2p_transfer"}:
        return "slide_right"
    if target in {"login", "register", "otp", "reset_pin", "splash"}:
        return "fade"
    return "fade"


def navigate(
    manager,
    target: str,
    previous: str = "",
    *,
    fallback: str = "login",
    transition_style: str | None = None,
) -> bool:
    if getattr(manager, "_cybercash_nav_busy", False):
        return False
    style = str(transition_style or "").strip() or resolve_transition_style(target, previous)
    if smooth_switch_screen(manager, target, style=style):
        return True
    if fallback:
        return smooth_switch_screen(manager, fallback, style="fade")
    return False
