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

    # Phase 3: host-side OpenClaw state directory that the `openclaw` binary
    # (invoked by app/services/fleet_cli.py) reads OPENCLAW_STATE_DIR from.
    # Fleet manages tenant config under `<openclaw_state_dir>/fleet/cells/<tenant>/`
    # itself (confirmed against docs.openclaw.ai/cli/fleet — see
    # docs/openclaw-integration-notes.md) — app/workers/provision_cell.py writes
    # rendered openclaw.json/vip-list.md directly into that directory rather than
    # passing a config path via a Fleet CLI flag (no such flag exists).
    openclaw_state_dir: str = "~/.openclaw"
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
