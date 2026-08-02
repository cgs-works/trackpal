from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict


@dataclass(frozen=True)
class ProtocolKeys:
    """Independent signing and encryption keys derived from one secret."""

    signing: bytes
    encryption: bytes


class EncryptedBody(BaseModel):
    """Base64-encoded AES-GCM payload components."""

    model_config = ConfigDict(extra="forbid")

    nonce: str
    ciphertext: str
