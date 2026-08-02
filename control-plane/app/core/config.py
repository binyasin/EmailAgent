from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # database
    database_url: str = "postgresql+psycopg://emailagent:emailagent@localhost:5432/emailagent"

    # auth
    jwt_secret_key: str = "change-me-dev-only"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # token custody — see app/services/secrets.py for how these are consumed
    # (current key + comma-separated retired keys still valid for decrypt)
    token_encryption_key: str = "change-me-dev-only-32-byte-fernet-key"
    token_encryption_key_previous: str = ""
    secrets_backend: str = "env"  # "env" | "vault" | "aws_kms" — see services/secrets.py

    # google oauth
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = "http://localhost:8000/api/v1/mailboxes/gmail/oauth/callback"

    # microsoft oauth (phase 2)
    ms_oauth_client_id: str = ""
    ms_oauth_client_secret: str = ""
    ms_oauth_tenant_id: str = "common"
    ms_oauth_redirect_uri: str = "http://localhost:8000/api/v1/mailboxes/outlook/oauth/callback"

    cors_allow_origins: list[str] = ["http://localhost:5173"]

    # Phase 3: local staging directory where rendered per-tenant config
    # (openclaw.json, vip-list.md) is written before being handed to Fleet —
    # see app/workers/provision_cell.py and the UNVERIFIED note in
    # app/services/fleet_cli.py about how Fleet actually expects to receive it.
    cell_state_root: str = "./.cell-state"
    default_cell_image: str = "openclaw/openclaw:latest"

    # billing — see app/services/billing.py
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id_starter: str = ""
    stripe_price_id_pro: str = ""
    stripe_price_id_enterprise: str = ""
    billing_success_url: str = "http://localhost:5173/billing?success=1"
    billing_cancel_url: str = "http://localhost:5173/billing?canceled=1"
    billing_portal_return_url: str = "http://localhost:5173/billing"


@lru_cache
def get_settings() -> Settings:
    return Settings()
