"""Key-material provider for the token-encryption key used by
`token_crypto.py` to encrypt/decrypt OAuth refresh tokens at rest.

Why this gets its own abstraction and most other secrets (JWT signing key,
OAuth client secrets, DATABASE_URL, ...) don't: those are naturally synced
from a secrets manager into the deployment's env vars/k8s Secret by
infra-level tooling (Vault Agent Injector, External Secrets Operator, etc.)
— see infra/k8s/helm/emailagent/values.yaml's `existingSecret` — and the app
keeps reading them via pydantic-settings exactly as it already does, with no
application code changes needed. The token-encryption key is different: it's
the single most sensitive secret in the system (compromise = every
connected mailbox's refresh token), and unlike the others it benefits from
**rotation without a flag day** — being able to decrypt data encrypted under
a retired key while encrypting new data under the current one. A bare env
var can't express "current key + still-valid-for-decrypting-old-data keys";
this abstraction can, using `cryptography`'s `MultiFernet`.

`EnvKeyProvider` is the only implemented backend. `VaultKeyProvider` and
`AwsKmsKeyProvider` are structural stubs — see their docstrings for what a
real implementation would need — left unimplemented rather than faked,
since there's no Vault/AWS environment available to build and verify
against here.
"""

from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings


class KeyProvider(Protocol):
    def get_encryption_keys(self) -> list[str]:
        """Returns Fernet keys, current key first. `token_crypto.py`
        encrypts with the first key and can decrypt with any of them —
        rotating means prepending a new current key and, once every
        actively-encrypted-under-the-old-key row has been re-encrypted or
        aged out, dropping the retired key from the list."""
        ...


class EnvKeyProvider:
    """Reads TOKEN_ENCRYPTION_KEY (current) and an optional
    TOKEN_ENCRYPTION_KEY_PREVIOUS (comma-separated retired keys, kept only
    long enough to decrypt rows that haven't been re-encrypted yet) from
    settings/env."""

    def get_encryption_keys(self) -> list[str]:
        settings = get_settings()
        keys = [settings.token_encryption_key]
        if settings.token_encryption_key_previous:
            keys += [
                k.strip()
                for k in settings.token_encryption_key_previous.split(",")
                if k.strip()
            ]
        return keys


class VaultKeyProvider:
    """NOT IMPLEMENTED. A real implementation would use Vault's Transit
    secrets engine (https://developer.hashicorp.com/vault/docs/secrets/transit):
    `get_encryption_keys` would call Transit's `export` endpoint for all
    versions of a named key (or, better, avoid exporting key material
    entirely and instead call Transit's `encrypt`/`decrypt` endpoints
    directly so the key material never leaves Vault — which would mean
    `token_crypto.py`'s interface needs to change from "give me a Fernet
    key" to "encrypt/decrypt this for me", a bigger refactor deferred until
    this is actually being built against a real Vault instance)."""

    def get_encryption_keys(self) -> list[str]:
        raise NotImplementedError(
            "VaultKeyProvider is a structural stub — see its docstring. "
            "Set SECRETS_BACKEND=env (the default) until this is implemented."
        )


class AwsKmsKeyProvider:
    """NOT IMPLEMENTED. A real implementation would use AWS KMS envelope
    encryption (GenerateDataKey / Decrypt) rather than exporting a raw
    Fernet key at all — same caveat as VaultKeyProvider about
    `token_crypto.py`'s interface needing to change to an encrypt/decrypt
    call rather than a "give me the key" call for a genuinely KMS-native
    integration."""

    def get_encryption_keys(self) -> list[str]:
        raise NotImplementedError(
            "AwsKmsKeyProvider is a structural stub — see its docstring. "
            "Set SECRETS_BACKEND=env (the default) until this is implemented."
        )


_BACKENDS: dict[str, type[KeyProvider]] = {
    "env": EnvKeyProvider,
    "vault": VaultKeyProvider,
    "aws_kms": AwsKmsKeyProvider,
}


@lru_cache
def get_key_provider() -> KeyProvider:
    backend = get_settings().secrets_backend
    provider_cls = _BACKENDS.get(backend)
    if provider_cls is None:
        raise ValueError(f"Unknown SECRETS_BACKEND '{backend}', must be one of {list(_BACKENDS)}")
    return provider_cls()
