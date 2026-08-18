from __future__ import annotations

from pathlib import Path


_ROOT_DIR = Path(__file__).resolve().parents[1]
_ASSETS_DIR = _ROOT_DIR / "assets"
_DATA_BUNDLE_ASSETS_DIR = _ASSETS_DIR / "data_bundle"


def data_bundle_asset_path(filename: str) -> str:
    """Return an absolute path to a bundled data-bundle asset."""

    return str(_DATA_BUNDLE_ASSETS_DIR / str(filename).strip())
