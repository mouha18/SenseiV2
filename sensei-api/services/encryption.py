import base64
import hashlib

from cryptography.fernet import Fernet

from config import get_settings


def _fernet() -> Fernet:
    settings = get_settings()
    derived_key = base64.urlsafe_b64encode(
        hashlib.sha256(settings.KEY_ENCRYPTION_SECRET.encode()).digest()
    )
    return Fernet(derived_key)


def encrypt_key(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_key(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()
