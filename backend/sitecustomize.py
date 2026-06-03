"""Backend Python startup hooks when commands run from the backend folder."""

from __future__ import annotations

import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from runtime_database_guard import install as _install_database_guard
except Exception:
    _install_database_guard = None

try:
    from runtime_money_guard import install as _install_money_guard
except Exception:
    _install_money_guard = None

if _install_database_guard is not None:
    _install_database_guard()

if _install_money_guard is not None:
    _install_money_guard()
