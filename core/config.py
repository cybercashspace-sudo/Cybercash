from __future__ import annotations

from dataclasses import dataclass

from core.environment import Environment, resolve_api_base_url, resolve_environment


@dataclass(frozen=True)
class Config:
    api_base_url: str = ""
    request_timeout: int = 15
    app_name: str = "CYBER CASH"
    cache_ttl: int = 300
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = True

    @classmethod
    def load(cls) -> "Config":
        environment = resolve_environment()
        return cls(
            api_base_url=resolve_api_base_url(),
            request_timeout=15,
            app_name="CYBER CASH",
            cache_ttl=300,
            environment=environment,
            debug=environment != Environment.PRODUCTION,
        )


AppConfig = Config


def get_config() -> Config:
    return Config.load()


config = get_config()
