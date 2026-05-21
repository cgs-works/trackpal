import base64
from typing import Optional
from cryptography.fernet import Fernet
from app.core.config import settings


def validate_encryption_key() -> None:
    """
    Validates that the DATA_ENCRYPTION_KEY in settings is configured and is a valid Fernet key.
    Raises ValueError if missing or invalid.
    """
    key = settings.data_encryption_key
    if not key:
        raise ValueError("DATA_ENCRYPTION_KEY is not set or is empty in configuration")
    try:
        # Check if it can be decoded and is a valid key for Fernet
        decoded = base64.urlsafe_b64decode(key)
        if len(decoded) != 32:
            raise ValueError("Key must be 32 bytes after base64 urlsafe decoding")
        Fernet(key.encode())
    except Exception as e:
        raise ValueError(f"DATA_ENCRYPTION_KEY is invalid: {str(e)}") from e


def get_fernet() -> Fernet:
    """
    Returns a configured Fernet instance.
    Raises ValueError if the key is missing or invalid.
    """
    validate_encryption_key()
    return Fernet(settings.data_encryption_key.encode())


def encrypt_value(value: Optional[str]) -> Optional[str]:
    """
    Encrypts a string value using Fernet.
    If value is None, returns None.
    """
    if value is None:
        return None
    fernet = get_fernet()
    return fernet.encrypt(value.encode()).decode()


def decrypt_value(token: Optional[str]) -> Optional[str]:
    """
    Decrypts a string value using Fernet.
    If token is None, returns None.
    """
    if token is None:
        return None
    fernet = get_fernet()
    return fernet.decrypt(token.encode()).decode()
