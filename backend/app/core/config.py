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

    # Order Email Scan: server-mediated OAuth so a connected mailbox's
    # refresh token can be stored (encrypted) and silently renewed instead of
    # re-prompting the user every scan. Google Cloud OAuth client (type "Web
    # application") and Azure App registration (platform "Web", not "Single-page
    # application" — a client secret is required for the server-side code
    # exchange) respectively.
    google_client_id: str = ""
    google_client_secret: str = ""
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    # Fernet key (44-char urlsafe-base64) used to encrypt stored refresh
    # tokens at rest and to sign the OAuth popup's CSRF state parameter.
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    token_encryption_key: str = ""
    # The label/folder a recorded order's email is moved into, per provider.
    gmail_orders_label: str = "Bead Store Orders"
    outlook_orders_label: str = "Bead Store Orders"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
