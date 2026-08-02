import base64
import hashlib
import hmac
import json
import os
from typing import cast
from uuid import UUID

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from pydantic import BaseModel

from app.protocol.models import EncryptedBody, ProtocolKeys

_PROTOCOL_SALT = b"trackpal-lookup-executor-protocol-v1"
_SIGNING_INFO = b"trackpal-lookup-executor-signing-v1"
_ENCRYPTION_INFO = b"trackpal-lookup-executor-encryption-v1"
_KEY_LENGTH = 32
_NONCE_LENGTH = 12


def derive_protocol_keys(secret: str) -> ProtocolKeys:
    """Derive independent HMAC and AES-GCM keys from an executor secret."""

    secret_bytes = secret.encode("utf-8")
    signing = _derive_key(secret_bytes, _SIGNING_INFO)
    encryption = _derive_key(secret_bytes, _ENCRYPTION_INFO)
    return ProtocolKeys(signing=signing, encryption=encryption)


def _derive_key(secret: bytes, info: bytes) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=_KEY_LENGTH,
        salt=_PROTOCOL_SALT,
        info=info,
    ).derive(secret)


def encrypt_payload(
    payload: BaseModel | dict[str, object], key: bytes
) -> EncryptedBody:
    """Encrypt a JSON payload with AES-GCM and a fresh 96-bit nonce."""

    data = (
        payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    )
    plaintext = json.dumps(
        data,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    nonce = os.urandom(_NONCE_LENGTH)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, associated_data=None)
    return EncryptedBody(
        nonce=base64.b64encode(nonce).decode("ascii"),
        ciphertext=base64.b64encode(ciphertext).decode("ascii"),
    )


def decrypt_payload(body: EncryptedBody, key: bytes) -> dict[str, object]:
    """Decrypt an AES-GCM body and return its JSON object payload."""

    nonce = base64.b64decode(body.nonce, validate=True)
    ciphertext = base64.b64decode(body.ciphertext, validate=True)
    plaintext = AESGCM(key).decrypt(nonce, ciphertext, associated_data=None)
    payload = json.loads(plaintext)
    if not isinstance(payload, dict):
        raise TypeError("encrypted payload must be a JSON object")
    return cast(dict[str, object], payload)


def sign_request(
    method: str,
    path: str,
    executor_id: UUID,
    key_version: int,
    timestamp: int,
    nonce: str,
    body_bytes: bytes,
    signing_key: bytes,
) -> str:
    """Sign the canonical request representation with HMAC-SHA256."""

    canonical = _canonical_request(
        method,
        path,
        executor_id,
        key_version,
        timestamp,
        nonce,
        body_bytes,
    )
    return hmac.new(signing_key, canonical, hashlib.sha256).hexdigest()


def verify_request_signature(
    method: str,
    path: str,
    executor_id: UUID,
    key_version: int,
    timestamp: int,
    nonce: str,
    body_bytes: bytes,
    signature: str,
    signing_key: bytes,
    now: int,
    max_skew_seconds: int,
) -> None:
    """Validate request freshness and its HMAC-SHA256 signature."""

    if abs(now - timestamp) > max_skew_seconds:
        raise ValueError("request timestamp outside allowed skew")

    expected = sign_request(
        method,
        path,
        executor_id,
        key_version,
        timestamp,
        nonce,
        body_bytes,
        signing_key,
    )
    if not hmac.compare_digest(signature, expected):
        raise ValueError("invalid request signature")


def _canonical_request(
    method: str,
    path: str,
    executor_id: UUID,
    key_version: int,
    timestamp: int,
    nonce: str,
    body_bytes: bytes,
) -> bytes:
    return "\n".join(
        [
            method.upper(),
            path,
            "1",
            str(executor_id),
            str(key_version),
            str(timestamp),
            nonce,
            hashlib.sha256(body_bytes).hexdigest(),
        ]
    ).encode("utf-8")
