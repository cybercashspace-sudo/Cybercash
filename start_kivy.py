import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PYTHON311 = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / "Python311"


def configure_runtime() -> None:
    site_paths = [
        PYTHON311 / "Lib" / "site-packages",
        ROOT / ".venv" / "Lib" / "site-packages",
    ]
    for path in reversed([str(path) for path in site_paths if path.exists()]):
        if path not in sys.path:
            sys.path.insert(0, path)

    dll_paths = [
        PYTHON311 / "share" / "sdl2" / "bin",
        PYTHON311 / "share" / "glew" / "bin",
        PYTHON311 / "share" / "angle" / "bin",
    ]
    for path in [str(path) for path in dll_paths if path.exists()]:
        os.environ["PATH"] = path + os.pathsep + os.environ.get("PATH", "")
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(path)

    os.environ.setdefault("CYBERCASH_KIVY_APP", "1")


def main() -> None:
    configure_runtime()
    from kivy_app import CyberCashApp

    CyberCashApp().run()


if __name__ == "__main__":
    main()
