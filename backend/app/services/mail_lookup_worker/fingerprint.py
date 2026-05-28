"""Deterministic fingerprint computation for deduplication.

Primary:  ``sha256(service_key + message_id + payload_normalized)``
Fallback: ``sha256(service_key + sender + received_at + subject + payload_normalized)``

Payload normalized is the extracted value itself — same code produces
same fingerprint regardless of email formatting differences.
"""

import hashlib


def compute_fingerprint(
    service_key: str,
    message_id: str | None,
    sender: str | None,
    received_at_iso: str,
    subject: str,
    payload_normalized: str,
) -> str:
    """Compute deterministic SHA-256 hex fingerprint for deduplication.

    Uses ``message_id`` when available (primary path).  Falls back to
    ``service_key + sender + received_at + subject + payload`` when
    ``message_id`` is ``None`` (e.g. IMAP messages without Message-ID
    header).
    """
    if message_id:
        raw = f"{service_key}|{message_id}|{payload_normalized}"
    else:
        sender_part = sender or "unknown"
        raw = (
            f"{service_key}|{sender_part}|{received_at_iso}|{subject}"
            f"|{payload_normalized}"
        )
    return hashlib.sha256(raw.encode()).hexdigest()


__all__ = ["compute_fingerprint"]
