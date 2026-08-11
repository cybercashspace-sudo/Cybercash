from __future__ import annotations

import os
from enum import Enum


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


def resolve_environment() -> Environment:
    raw = str(os.getenv("CYBERCASH_ENV", os.getenv("APP_ENV", "development")) or "").strip().lower()
    if raw in {Environment.STAGING.value, "stage"}:
        return Environment.STAGING
    if raw in {Environment.PRODUCTION.value, "prod", "live"}:
        return Environment.PRODUCTION
    return Environment.DEVELOPMENT


def resolve_api_base_url() -> str:
    env = resolve_environment()
    if env == Environment.PRODUCTION:
        return "https://api.cybercash.space"
    if env == Environment.STAGING:
        return "https://staging-api.cybercash.space"
    return "https://dev-api.cybercash.space"

