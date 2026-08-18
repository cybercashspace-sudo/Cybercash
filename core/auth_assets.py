from __future__ import annotations

from pathlib import Path


_ROOT_DIR = Path(__file__).resolve().parents[1]
_ASSETS_DIR = _ROOT_DIR / "assets"
_AUTH_ASSETS_DIR = _ASSETS_DIR / "auth"


def asset_path(filename: str) -> str:
    """Return an absolute path to a bundled asset."""

    return str(_ASSETS_DIR / str(filename).strip())


def auth_asset_path(filename: str) -> str:
    """Return an absolute path to a bundled auth-screen asset."""

    return str(_AUTH_ASSETS_DIR / str(filename).strip())
