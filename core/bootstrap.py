from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def ensure_runtime_bootstrap(root_dir: Path | None = None) -> Path:
    """Ensure the project root and local theme package are importable.

    Android startup can miss the repository root on sys.path early in boot.
    We normalize that here and load the local ``theme`` package explicitly so
    feature modules can import it reliably on every launcher path.
    """

    root = Path(root_dir or Path(__file__).resolve().parents[1]).resolve()
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)

    if "theme" in sys.modules:
        return root

    package_dir = root / "theme"
    init_file = package_dir / "__init__.py"
    if not init_file.exists():
        return root

    spec = importlib.util.spec_from_file_location(
        "theme",
        init_file,
        submodule_search_locations=[str(package_dir)],
    )
    if spec is None or spec.loader is None:
        return root

    module = importlib.util.module_from_spec(spec)
    sys.modules["theme"] = module
    spec.loader.exec_module(module)
    return root
