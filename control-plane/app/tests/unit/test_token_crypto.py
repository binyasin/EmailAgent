from cryptography.fernet import Fernet

from app.core.config import get_settings
from app.services.token_crypto import decrypt_token, encrypt_token


def test_encrypt_decrypt_roundtrip():
    plaintext = "super-secret-refresh-token"
    ciphertext = encrypt_token(plaintext)

    assert ciphertext != plaintext
    assert decrypt_token(ciphertext) == plaintext


def test_ciphertext_is_not_deterministic():
    # Fernet includes a random IV, so encrypting the same plaintext twice
    # must not produce the same ciphertext (defends against a regression to
    # a non-random/ECB-style scheme).
    plaintext = "same-secret"
    assert encrypt_token(plaintext) != encrypt_token(plaintext)


def test_rotation_can_still_decrypt_data_encrypted_under_a_retired_key(monkeypatch):
    settings = get_settings()
    old_key = settings.token_encryption_key

    ciphertext_under_old_key = encrypt_token("token-encrypted-before-rotation")

    # Rotate: a brand new current key, old key demoted to "previous".
    new_key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "token_encryption_key", new_key)
    monkeypatch.setattr(settings, "token_encryption_key_previous", old_key)

    # Still-valid old ciphertext must decrypt...
    assert decrypt_token(ciphertext_under_old_key) == "token-encrypted-before-rotation"
    # ...and new encryptions use (and round-trip under) the new current key.
    new_ciphertext = encrypt_token("token-encrypted-after-rotation")
    assert decrypt_token(new_ciphertext) == "token-encrypted-after-rotation"
