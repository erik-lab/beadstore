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

    # Verify TLS against the OS certificate store instead of Python's own
    # bundle — see app/core/trust.py. Needed only on a machine that
    # intercepts HTTPS; leave off on a server.
    use_system_trust_store: bool = False

    # Where uploaded product photos live — see app/core/storage.py.
    # "local" writes to storage_local_root, which is right for development and
    # wrong for Render, whose filesystem doesn't survive a deploy. "s3" points
    # at Supabase Storage's S3 endpoint with storage-scoped access keys (NOT
    # the service-role key, which could bypass every database policy).
    storage_backend: str = "local"
    storage_local_root: str = "./var/uploads"
    storage_s3_endpoint_url: str = ""
    # No default on purpose. The region is part of what an AWS SigV4 request
    # signs, so a plausible-looking wrong value doesn't fail as a region
    # error — it fails as HTTP 403, indistinguishable from a bad secret. A
    # default of "us-east-1" cost an afternoon exactly that way. Copy it from
    # the S3 Configuration page beside the endpoint.
    storage_s3_region: str = ""
    storage_s3_bucket: str = ""
    storage_s3_access_key_id: str = ""
    storage_s3_secret_access_key: str = ""
    # Path to a CA bundle for the S3 connection, for a machine where HTTPS is
    # intercepted (corporate proxy, VPN, antivirus TLS scanning) and Python
    # doesn't trust the substituted certificate. A setting rather than
    # botocore's AWS_CA_BUNDLE environment variable because this project's
    # configuration lives in .env, which pydantic-settings reads into
    # Settings without exporting to os.environ — so AWS_CA_BUNDLE put there
    # would be silently ignored. Empty means use the default trust store.
    storage_s3_ca_bundle: str = ""
    # Set only for a public bucket: images are then served straight from the
    # CDN instead of streaming through this process.
    storage_public_base_url: str = ""

    # Etsy integration (see docs/design/api-tiers-work-plan.md Phase 3).
    #
    # Real Etsy splits these across THREE hosts, so they're three settings:
    #   authorize  https://www.etsy.com/oauth/connect        (seller consent page)
    #   token      https://api.etsy.com/v3/public/oauth/token
    #   API        https://openapi.etsy.com/v3/application/...
    # Each is an origin only — the code appends the versioned path, so a base
    # with /v3 already on it produces /v3/v3/... and 404s.
    #
    # Locally all three point at this same server's built-in simulator
    # (etsy_simulator_enabled=true), which mirrors the same relative paths, so
    # the integration code can be exercised without live Etsy credentials.
    etsy_client_id: str = ""
    etsy_client_secret: str = ""
    etsy_authorize_base_url: str = "https://www.etsy.com"
    etsy_token_base_url: str = "https://api.etsy.com"
    etsy_api_base_url: str = "https://openapi.etsy.com"
    etsy_webhook_signing_secret: str = ""
    etsy_simulator_enabled: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
