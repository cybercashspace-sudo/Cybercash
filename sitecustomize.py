"""Project Python startup hooks."""

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent
root_text = str(ROOT_DIR)
if root_text not in sys.path:
    sys.path.insert(0, root_text)

try:
    from core.bootstrap import ensure_runtime_bootstrap as _ensure_runtime_bootstrap
except Exception:
    _ensure_runtime_bootstrap = None
else:
    try:
        _ensure_runtime_bootstrap(ROOT_DIR)
    except Exception:
        pass

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
