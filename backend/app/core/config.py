from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "MarketPulse AI"
    environment: str = "local"
    database_url: str = "postgresql+psycopg://marketpulse:marketpulse@localhost:5432/marketpulse"
    cors_origins: list[str] = ["http://localhost:5173"]
    log_level: str = "INFO"

    # Background scheduling. Off by default so local runs and tests only sync when asked.
    scheduler_enabled: bool = False
    sync_interval_minutes: int = 60

    csv_max_bytes: int = 10 * 1024 * 1024
    csv_max_rows: int = 50_000

    # Bluesky: public AppView by default. If a handle and app password are set, the
    # connector signs in and searches through the authenticated host instead.
    bluesky_public_base: str = "https://public.api.bsky.app"
    bluesky_auth_base: str = "https://bsky.social"
    bluesky_handle: str | None = None
    bluesky_app_password: str | None = None
    bluesky_max_queries: int = 25
    bluesky_max_pages: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
