import pytest

from app.core.config import get_settings
from app.services.secrets import (
    AwsKmsKeyProvider,
    EnvKeyProvider,
    VaultKeyProvider,
    get_key_provider,
)


def test_env_key_provider_returns_only_current_key_by_default():
    provider = EnvKeyProvider()
    assert provider.get_encryption_keys() == [get_settings().token_encryption_key]


def test_env_key_provider_includes_previous_keys_for_rotation(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "token_encryption_key", "current-key")
    monkeypatch.setattr(settings, "token_encryption_key_previous", "old-key-1, old-key-2")

    provider = EnvKeyProvider()
    assert provider.get_encryption_keys() == ["current-key", "old-key-1", "old-key-2"]


def test_vault_and_aws_providers_are_unimplemented_stubs():
    with pytest.raises(NotImplementedError):
        VaultKeyProvider().get_encryption_keys()
    with pytest.raises(NotImplementedError):
        AwsKmsKeyProvider().get_encryption_keys()


def test_get_key_provider_rejects_unknown_backend(monkeypatch):
    get_key_provider.cache_clear()
    monkeypatch.setattr(get_settings(), "secrets_backend", "not-a-real-backend")
    with pytest.raises(ValueError, match="Unknown SECRETS_BACKEND"):
        get_key_provider()
    get_key_provider.cache_clear()  # don't leak the failed cache-miss state into other tests
