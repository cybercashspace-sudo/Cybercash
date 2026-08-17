"""Reusable animated UI components for CYBER CASH.

This package uses lazy re-exports so importing ``components`` does not eagerly
load the full widget graph during Android startup.
"""

from __future__ import annotations

from importlib import import_module

_EXPORTS: dict[str, tuple[str, str]] = {
    "AnimatedButton": ("animated_button", "AnimatedButton"),
    "AnimatedCard": ("animated_card", "AnimatedCard"),
    "AnimatedWalletCard": ("animated_wallet_card", "AnimatedWalletCard"),
    "AppButton": ("app_button", "AppButton"),
    "AppDialog": ("app_dialog", "AppDialog"),
    "AppIconButton": ("app_icon_button", "AppIconButton"),
    "AppSnackbar": ("app_snackbar", "AppSnackbar"),
    "AppToolbar": ("app_toolbar", "AppToolbar"),
    "AppTextField": ("app_textfield", "AppTextField"),
    "AmountLabel": ("amount_label", "AmountLabel"),
    "BalanceCounter": ("balance_counter", "BalanceCounter"),
    "BalanceLabel": ("balance_label", "BalanceLabel"),
    "BottomNav": ("bottom_nav", "BottomNav"),
    "BottomNavBar": ("bottom_nav", "BottomNavBar"),
    "EmptyState": ("empty_state", "EmptyState"),
    "LoadingSkeleton": ("loading_skeleton", "LoadingSkeleton"),
    "NotificationBadge": ("notification_badge", "NotificationBadge"),
    "ProfileAvatar": ("profile_avatar", "ProfileAvatar"),
    "QuickAction": ("quick_action", "QuickAction"),
    "QuickActionButton": ("quick_action_button", "QuickActionButton"),
    "RefreshIndicator": ("refresh_indicator", "RefreshIndicator"),
    "SectionHeader": ("section_header", "SectionHeader"),
    "StatusChip": ("status_chip", "StatusChip"),
    "TransactionCard": ("transaction_card", "TransactionCard"),
    "WalletCard": ("wallet_card", "WalletCard"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    module = import_module(f".{module_name}", __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(_EXPORTS))
