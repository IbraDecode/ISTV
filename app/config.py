from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql://localhost:5432/istv"
    secret_key: str = "change-me"
    api_rate_limit: int = 100
    api_rate_window: int = 60
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "*"
    environment: str = "production"
    log_level: str = "info"
    m3u_url: str = ""
    epg_url: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
