"""Real HTTP callback capture server for the worker/backend contract test."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from uuid import UUID

from app.core.lookup_executor_protocol import (
    decrypt_payload,
    derive_protocol_keys,
    verify_request_signature,
)
from app.schemas.lookup_executor_protocol import EncryptedBody, LookupCallbackEnvelope


@dataclass(frozen=True, slots=True)
class CapturedCallback:
    """Callback payload accepted after backend protocol verification."""

    path: str
    envelope: LookupCallbackEnvelope


class CallbackCaptureServer:
    """Capture and verify one callback over a real loopback HTTP connection."""

    def __init__(self, executor_id: UUID, executor_secret: str) -> None:
        self._executor_id = executor_id
        self._keys = derive_protocol_keys(executor_secret)
        self._callback: CapturedCallback | None = None
        self._error: Exception | None = None
        self._event = threading.Event()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
                owner._handle(self)

            def log_message(self, *_args: object) -> None:
                return None

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="contract-callback-server",
            daemon=True,
        )

    @property
    def url(self) -> str:
        """Return the loopback base URL of the capture server."""
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def start(self) -> None:
        """Start accepting callback requests."""
        self._thread.start()

    def close(self) -> None:
        """Stop the callback server and release its listening socket."""
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def wait_for_callback(self, timeout: float = 10.0) -> CapturedCallback:
        """Wait for a verified callback or raise its protocol error."""
        if not self._event.wait(timeout):
            raise AssertionError("worker callback was not received")
        if self._error is not None:
            raise AssertionError("backend rejected worker callback") from self._error
        assert self._callback is not None
        return self._callback

    def _handle(self, request: BaseHTTPRequestHandler) -> None:
        try:
            body = request.rfile.read(int(request.headers["Content-Length"]))
            executor_id = UUID(request.headers["X-TrackPal-Executor-Id"])
            key_version = int(request.headers["X-TrackPal-Key-Version"])
            timestamp = int(request.headers["X-TrackPal-Timestamp"])
            nonce = request.headers["X-TrackPal-Nonce"]
            signature = request.headers["X-TrackPal-Signature"]
            if executor_id != self._executor_id or key_version != 1:
                raise ValueError("invalid callback identity")
            verify_request_signature(
                "POST",
                urlsplit(request.path).path,
                executor_id,
                key_version,
                timestamp,
                nonce,
                body,
                signature,
                self._keys.signing,
                now=int(time.time()),
                max_skew_seconds=60,
            )
            encrypted = EncryptedBody.model_validate_json(body)
            payload = decrypt_payload(encrypted, self._keys.encryption)
            envelope = LookupCallbackEnvelope.model_validate(payload)
            self._callback = CapturedCallback(
                path=urlsplit(request.path).path,
                envelope=envelope,
            )
            response_body = json.dumps({"accepted": True}).encode("utf-8")
            request.send_response(200)
        except Exception as exc:  # pragma: no cover - asserted through wait helper
            self._error = exc
            response_body = json.dumps({"accepted": False}).encode("utf-8")
            request.send_response(400)
        finally:
            self._event.set()
            request.send_header("Content-Type", "application/json")
            request.send_header("Content-Length", str(len(response_body)))
            request.end_headers()
            request.wfile.write(response_body)


__all__ = ["CallbackCaptureServer", "CapturedCallback"]
