import os
import sys
from pathlib import Path

from core.bootstrap import ensure_runtime_bootstrap


ROOT = Path(__file__).resolve().parent
PYTHON311 = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / "Python311"


def _prepend_runtime_path(path: Path) -> None:
    if not path.exists():
        return
    raw_path = str(path)
    path_parts = os.environ.get("PATH", "").split(os.pathsep)
    if raw_path not in path_parts:
        os.environ["PATH"] = raw_path + os.pathsep + os.environ.get("PATH", "")
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(raw_path)


def configure_runtime() -> None:
    os.environ.setdefault("KIVY_HOME", str(ROOT / ".kivy_runtime"))

    site_paths = [
        ROOT / ".venv" / "Lib" / "site-packages",
        PYTHON311 / "Lib" / "site-packages",
    ]
    for path in reversed([str(path) for path in site_paths if path.exists()]):
        if path not in sys.path:
            sys.path.insert(0, path)

    dll_paths = [
        ROOT / ".python310_lib_full",
        ROOT / ".python310_lib_full" / "DLLs",
        ROOT / ".venv" / "share" / "sdl2" / "bin",
        ROOT / ".venv" / "share" / "glew" / "bin",
        ROOT / ".venv" / "share" / "angle" / "bin",
        ROOT / "share" / "sdl2" / "bin",
        ROOT / "share" / "glew" / "bin",
        ROOT / "share" / "angle" / "bin",
        PYTHON311 / "share" / "sdl2" / "bin",
        PYTHON311 / "share" / "glew" / "bin",
        PYTHON311 / "share" / "angle" / "bin",
    ]
    for path in dll_paths:
        _prepend_runtime_path(path)

    os.environ.setdefault("CYBERCASH_KIVY_APP", "1")


def main() -> None:
    configure_runtime()
    ensure_runtime_bootstrap(ROOT)
    from kivy_app import CyberCashApp

    CyberCashApp().run()


if __name__ == "__main__":
    main()
