from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "local"
    database_url: str = "sqlite:///./beadstore_dev.db"
    database_url_migrations: str = ""
    supabase_url: str = ""
    supabase_jwt_secret: str = "dev-secret-change-me"
    supabase_jwt_audience: str = "authenticated"
    allow_public_signup: bool = False
    cors_origins: str = "http://localhost:5173"
    # Enables AI-assisted order email parsing (Order Email Scan → Record Order).
    anthropic_api_key: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
