import os
import sys


def _is_backend_runtime() -> bool:
    if str(os.getenv("CYBERCASH_KIVY_APP", "")).strip().lower() in {"1", "true", "yes"}:
        return False

    args = " ".join(str(arg or "").lower() for arg in sys.argv)
    if "gunicorn" in args or "uvicorn" in args:
        return True

    render_markers = (
        "RENDER",
        "RENDER_SERVICE_ID",
        "RENDER_EXTERNAL_URL",
        "RENDER_GIT_COMMIT",
    )
    if any(os.getenv(name) for name in render_markers):
        return True

    return bool(os.getenv("PORT") and str(os.getenv("ENV", "")).strip().lower() == "production")


if _is_backend_runtime():
    from backend.main import app
else:
    from kivy_app import CyberCashApp

    app = None
