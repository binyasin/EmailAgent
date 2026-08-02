from cryptography.fernet import Fernet, MultiFernet

from app.services.secrets import get_key_provider


def _multi_fernet() -> MultiFernet:
    keys = get_key_provider().get_encryption_keys()
    # MultiFernet encrypts with the first key and can decrypt with any of
    # them — this is what makes key rotation possible without a flag day:
    # prepend a new current key, keep the old one in the "previous" list
    # until every row encrypted under it has been re-encrypted or aged out.
    return MultiFernet([Fernet(k.encode() if isinstance(k, str) else k) for k in keys])


def encrypt_token(plaintext: str) -> str:
    return _multi_fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    return _multi_fernet().decrypt(ciphertext.encode()).decode()
