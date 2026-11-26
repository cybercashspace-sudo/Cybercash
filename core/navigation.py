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
    if manager is None:
        return False

    target = str(target or "").strip()
    if not target:
        return False

    if getattr(manager, "_cybercash_nav_busy", False):
        pending = str(getattr(manager, "_cybercash_pending_target", "") or "").strip()
        return pending == target

    style = str(transition_style or "").strip() or resolve_transition_style(target, previous)
    if smooth_switch_screen(manager, target, style=style):
        return True
    if fallback:
        return smooth_switch_screen(manager, fallback, style="fade")
    return False


def navigate_back(owner) -> bool:
    """Dismiss the active popup, or return to the actual previous screen."""
    dialog = getattr(owner, "_active_dialog", None)
    if dialog is not None:
        try:
            dialog.dismiss()
        except Exception:
            pass
        return True

    manager = getattr(owner, "manager", None)
    if manager is None or getattr(manager, "_cybercash_nav_busy", False):
        return False

    current = str(getattr(manager, "current", "") or "").strip()
    history = list(getattr(manager, "_cybercash_screen_history", []) or [])
    target = ""
    fallback_target = str(getattr(manager, "_cybercash_back_fallback_target", "") or "").strip()
    if not history and fallback_target and current == fallback_target:
        return False
    while history:
        candidate = str(history[-1] or "").strip()
        if candidate and candidate != current and candidate != "splash" and manager.has_screen(candidate):
            target = candidate
            break
        history.pop()
    target_from_history = bool(target)
    if target:
        manager._cybercash_screen_history = history
    else:
        candidate = str(getattr(manager, "previous_screen", "") or "").strip()
        if candidate and candidate != current and candidate != "splash" and manager.has_screen(candidate):
            target = candidate

    if not target:
        return False

    manager._cybercash_back_navigation = True
    try:
        navigated = navigate(
            manager,
            target,
            fallback="",
            transition_style="slide_right",
        )
        if navigated and not target_from_history:
            manager._cybercash_back_fallback_target = target
        return navigated
    finally:
        manager._cybercash_back_navigation = False
