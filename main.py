import importlib.util
import sys
from pathlib import Path

from kivy.core.window import Window


ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _bootstrap_theme_package() -> None:
    """Ensure the local theme package is importable before app startup."""

    if "theme" in sys.modules:
        return

    package_dir = ROOT_DIR / "theme"
    init_file = package_dir / "__init__.py"
    if not init_file.exists():
        return

    spec = importlib.util.spec_from_file_location(
        "theme",
        init_file,
        submodule_search_locations=[str(package_dir)],
    )
    if spec is None or spec.loader is None:
        return

    module = importlib.util.module_from_spec(spec)
    sys.modules["theme"] = module
    spec.loader.exec_module(module)


_bootstrap_theme_package()

from kivy_app import CyberCashApp

Window.softinput_mode = "resize"


if __name__ == "__main__":
    CyberCashApp().run()
