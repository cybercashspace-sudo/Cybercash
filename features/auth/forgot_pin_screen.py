from __future__ import annotations

from screens.reset_pin import ResetPinScreen as _LegacyResetPinScreen


class ForgotPinScreen(_LegacyResetPinScreen):
    """Compatibility wrapper for the existing reset PIN flow."""

