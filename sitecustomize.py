"""Project Python startup hooks."""

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
