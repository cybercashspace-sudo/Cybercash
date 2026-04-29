from __future__ import annotations

import importlib.util
import subprocess
import sys
import threading
import time
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _runner_path() -> Path | None:
    runner = _project_root() / "kivy_frontend" / "paystack_webview_runner.py"
    return runner if runner.exists() else None


_PROJECT_ROOT = _project_root()
_RUNNER = _runner_path()
_HAS_WEBVIEW = importlib.util.find_spec("webview") is not None and _RUNNER is not None
_WARMUP_STARTED = False
_WARMUP_LOCK = threading.Lock()


def _resolve_python_executable() -> str:
    python_exe = sys.executable or "python"

    if sys.platform.startswith("win"):
        try:
            python_path = Path(python_exe)
            pythonw = python_path.with_name("pythonw.exe")
            if pythonw.exists():
                return str(pythonw)
        except Exception:
            pass

    return python_exe


def _popen_detached(args: list[str]) -> None:
    kwargs: dict = {
        "cwd": str(_PROJECT_ROOT),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }

    if sys.platform.startswith("win"):
        kwargs["creationflags"] = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))

    subprocess.Popen(args, **kwargs)


def warmup_paystack_checkout(*, delay_seconds: float = 0.0) -> bool:
    """Preload the in-app checkout runtime in the background.

    This runs a lightweight "warmup" subprocess that imports pywebview once so the
    first real checkout window opens faster on slower devices.
    """

    global _WARMUP_STARTED
    if not _HAS_WEBVIEW or _RUNNER is None:
        return False

    with _WARMUP_LOCK:
        if _WARMUP_STARTED:
            return True
        _WARMUP_STARTED = True

    python_exe = _resolve_python_executable()
    launch_args = [python_exe, str(_RUNNER), "--warmup"]

    def _launch() -> None:
        try:
            delay = float(delay_seconds or 0.0)
            if delay > 0:
                time.sleep(delay)
            _popen_detached(launch_args)
        except Exception:
            pass

    threading.Thread(target=_launch, daemon=True).start()
    return True


def open_paystack_checkout(url: str, title: str = "CYBER CASH Checkout", delay_seconds: float = 0.0) -> bool:
    url = str(url or "").strip()
    if not url:
        return False

    if not _HAS_WEBVIEW:
        return False

    python_exe = _resolve_python_executable()
    launch_args = [
        python_exe,
        str(_RUNNER),
        "--url",
        url,
        "--title",
        str(title or "CYBER CASH Checkout"),
    ]

    def _launch() -> None:
        try:
            delay = float(delay_seconds or 0.0)
            if delay > 0:
                time.sleep(delay)
            _popen_detached(launch_args)
        except Exception:
            pass

    threading.Thread(target=_launch, daemon=True).start()
    return True
