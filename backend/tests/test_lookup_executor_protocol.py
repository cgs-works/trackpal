"""Protocol v1 compatibility tests for the backend implementation."""

from uuid import UUID

import pytest
from cryptography.exceptions import InvalidTag

from app.core.lookup_executor_protocol import (
    decrypt_payload,
    derive_protocol_keys,
    encrypt_payload,
    sign_request,
    verify_request_signature,
)
from app.schemas.lookup_executor_protocol import EncryptedBody


EXECUTOR_ID = UUID("00000000-0000-0000-0000-000000000001")


def test_protocol_matches_worker_signature_fixture() -> None:
    body = b'{"job_id":"job-1"}'
    signature = sign_request(
        "post",
        "/v1/jobs",
        EXECUTOR_ID,
        3,
        1_700_000_000,
        "nonce-1",
        body,
        b"signing-key",
    )

    assert signature == (
        "4b9b25ada7483d3e5f76171b2fa2e17ebe5e9cd89d8110ef7ccbd70dbd4a1cf9"
    )
    verify_request_signature(
        "POST",
        "/v1/jobs",
        EXECUTOR_ID,
        3,
        1_700_000_000,
        "nonce-1",
        body,
        signature,
        b"signing-key",
        now=1_700_000_030,
        max_skew_seconds=60,
    )


def test_protocol_decrypts_literal_worker_ciphertext_fixture() -> None:
    keys = derive_protocol_keys("executor-secret")
    encrypted = EncryptedBody(
        nonce="AAAAAAAAAAAAAAAA",
        ciphertext="glETUFCCrWSwjVB89YTfmVpcz4L/zNYtZp2+pPOcSAlQzg==",
    )

    assert decrypt_payload(encrypted, keys.encryption) == {"job_id": "job-1"}


def test_protocol_encryption_round_trip_uses_aes_gcm() -> None:
    keys = derive_protocol_keys("executor-secret")
    encrypted = encrypt_payload({"job_id": "job-1"}, keys.encryption)

    assert decrypt_payload(encrypted, keys.encryption) == {"job_id": "job-1"}
    assert len(encrypted.nonce) == 16


def test_protocol_rejects_changed_path_and_tampered_ciphertext() -> None:
    body = b'{"job_id":"job-1"}'
    signature = sign_request(
        "POST", "/v1/jobs", EXECUTOR_ID, 1, 1_700_000_000, "nonce", body, b"key"
    )

    with pytest.raises(ValueError, match="signature"):
        verify_request_signature(
            "POST",
            "/v1/jobs/changed",
            EXECUTOR_ID,
            1,
            1_700_000_000,
            "nonce",
            body,
            signature,
            b"key",
            now=1_700_000_000,
            max_skew_seconds=60,
        )

    keys = derive_protocol_keys("executor-secret")
    encrypted = encrypt_payload({"job_id": "job-1"}, keys.encryption)
    tampered = EncryptedBody(
        nonce=encrypted.nonce,
        ciphertext=encrypted.ciphertext[:-2] + "AA",
    )
    with pytest.raises(InvalidTag):
        decrypt_payload(tampered, keys.encryption)
