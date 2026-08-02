import hashlib
from uuid import UUID

import pytest
from cryptography.exceptions import InvalidTag
from pydantic import BaseModel

from app.protocol.crypto import (
    decrypt_payload,
    derive_protocol_keys,
    encrypt_payload,
    sign_request,
    verify_request_signature,
)
from app.protocol.models import EncryptedBody
from app.protocol.replay import NonceCache


class LookupPayload(BaseModel):
    job_id: str


def test_protocol_keys_are_deterministic_and_separated() -> None:
    first = derive_protocol_keys("executor-secret")
    second = derive_protocol_keys("executor-secret")
    other = derive_protocol_keys("other-secret")

    assert first == second
    assert first.signing != first.encryption
    assert first.signing != other.signing
    assert first.encryption != other.encryption


def test_payload_round_trips_for_dict_and_pydantic_model() -> None:
    keys = derive_protocol_keys("executor-secret")

    encrypted_dict = encrypt_payload({"job_id": "job-1"}, keys.encryption)
    encrypted_model = encrypt_payload(LookupPayload(job_id="job-2"), keys.encryption)

    assert decrypt_payload(encrypted_dict, keys.encryption) == {"job_id": "job-1"}
    assert decrypt_payload(encrypted_model, keys.encryption) == {"job_id": "job-2"}
    assert encrypted_dict.nonce != encrypted_model.nonce


def test_tampered_ciphertext_is_rejected() -> None:
    keys = derive_protocol_keys("executor-secret")
    body = encrypt_payload({"job_id": "job-1"}, keys.encryption)
    tampered = EncryptedBody(
        nonce=body.nonce,
        ciphertext=body.ciphertext[:-2] + "AA",
    )

    with pytest.raises(InvalidTag):
        decrypt_payload(tampered, keys.encryption)


def test_request_signature_uses_exact_canonical_representation() -> None:
    body = b'{"job_id":"job-1"}'
    executor_id = UUID("00000000-0000-0000-0000-000000000001")
    signature = sign_request(
        "post",
        "/v1/jobs",
        executor_id,
        3,
        1_700_000_000,
        "nonce-1",
        body,
        b"signing-key",
    )

    assert (
        signature == "4b9b25ada7483d3e5f76171b2fa2e17ebe5e9cd89d8110ef7ccbd70dbd4a1cf9"
    )

    verify_request_signature(
        "POST",
        "/v1/jobs",
        executor_id,
        3,
        1_700_000_000,
        "nonce-1",
        body,
        signature,
        b"signing-key",
        now=1_700_000_030,
        max_skew_seconds=60,
    )


def test_request_signature_rejects_tampering_and_clock_skew() -> None:
    body = b'{"job_id":"job-1"}'
    executor_id = UUID("00000000-0000-0000-0000-000000000001")
    signature = sign_request(
        "POST",
        "/v1/jobs",
        executor_id,
        3,
        1_700_000_000,
        "nonce-1",
        body,
        b"signing-key",
    )

    with pytest.raises(ValueError, match="signature"):
        verify_request_signature(
            "POST",
            "/v1/jobs/changed",
            executor_id,
            3,
            1_700_000_000,
            "nonce-1",
            body,
            signature,
            b"signing-key",
            now=1_700_000_030,
            max_skew_seconds=60,
        )

    with pytest.raises(ValueError, match="timestamp"):
        verify_request_signature(
            "POST",
            "/v1/jobs",
            executor_id,
            3,
            1_700_000_000,
            "nonce-1",
            body,
            signature,
            b"signing-key",
            now=1_700_000_061,
            max_skew_seconds=60,
        )


def test_nonce_cache_rejects_second_use() -> None:
    cache = NonceCache(ttl_seconds=60, max_entries=100)

    assert cache.consume("nonce-1", now=1000) is True
    assert cache.consume("nonce-1", now=1001) is False


def test_nonce_cache_rejects_new_nonce_when_full_without_evicting_valid_entries() -> None:
    cache = NonceCache(ttl_seconds=10, max_entries=2)

    assert cache.consume("nonce-1", now=1000) is True
    assert cache.consume("nonce-2", now=1001) is True
    assert cache.consume("nonce-3", now=1002) is False
    assert cache.consume("nonce-1", now=1002) is False
    assert cache.consume("nonce-2", now=1002) is False
    assert cache.consume("nonce-1", now=1010) is True


def test_request_body_hash_fixture_is_stable() -> None:
    assert hashlib.sha256(b'{"job_id":"job-1"}').hexdigest() == (
        "2419aba9857b5e95a5e3a510c74ce961a9bc208eaf25fb10abd269ba7ba7d0d0"
    )
