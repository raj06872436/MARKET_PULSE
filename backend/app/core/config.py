from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "MarketPulse AI"
    environment: str = "local"
    database_url: str = "postgresql+psycopg://marketpulse:marketpulse@localhost:5432/marketpulse"
    cors_origins: list[str] = ["http://localhost:5173"]
    log_level: str = "INFO"
    # Set in the production image: the built frontend is served from here, on the same origin as the API.
    static_dir: str | None = None
    db_pool_size: int = 5

    # Background scheduling. Off by default so local runs and tests only sync when asked.
    scheduler_enabled: bool = False
    sync_interval_minutes: int = 60

    # "auto" uses whichever model the latest evaluation selected (app/ml/sentiment/evaluation.json).
    sentiment_model: str = "auto"

    # Insight cards. Template cards always work. Set INSIGHTS_LLM_ENABLED=true and ANTHROPIC_API_KEY to let
    # Claude write them from the same validated facts; anything that fails validation falls back to templates.
    insights_llm_enabled: bool = False
    anthropic_api_key: str | None = None
    insights_model: str = "claude-opus-5-5"

    # Sign-in. Sessions last this many days from the last request. Set ALLOW_REGISTRATION=false once the
    # accounts you need exist; the first account created becomes the admin.
    session_days: int = 14
    allow_registration: bool = True
    # Secure cookies need HTTPS. They are on everywhere except ENVIRONMENT=local unless set explicitly.
    cookie_secure: bool | None = None

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


    @field_validator("database_url")
    @classmethod
    def use_psycopg_driver(cls, value: str) -> str:
        """Hosted databases hand out postgres:// URLs; SQLAlchemy needs the driver named."""
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value.removeprefix(prefix)
        return value

    @property
    def secure_cookies(self) -> bool:
        return self.cookie_secure if self.cookie_secure is not None else self.environment != "local"


@lru_cache
def get_settings() -> Settings:
    return Settings()
