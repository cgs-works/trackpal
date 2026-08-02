"""Cross-process protocol contract coverage for the external lookup executor."""

from __future__ import annotations

import asyncio
import os
import socket
import subprocess
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.core.encryption import encrypt_value
from app.services.lookup_executor_transport.http import HttpLookupExecutorTransport

from .contract_callback_server import CallbackCaptureServer


BACKEND_ROOT = Path(__file__).resolve().parents[1]
WORKER_ROOT = BACKEND_ROOT.parent / "worker"
EXECUTOR_ID = UUID("00000000-0000-0000-0000-000000000015")
EXECUTOR_SECRET = "contract-executor-secret"


class LoopbackResolver:
    """Test-only resolver that explicitly permits the local contract server."""

    allow_loopback = True

    def resolve(self, _host: str, _port: int) -> list[str]:
        return ["127.0.0.1"]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _executor(port: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=EXECUTOR_ID,
        base_url=f"http://127.0.0.1:{port}",
        transport_mode="http_encrypted",
        secret_encrypted=encrypt_value(EXECUTOR_SECRET),
        secret_version=1,
    )


@pytest.mark.asyncio
async def test_worker_and_backend_complete_real_signed_contract() -> None:
    """Verify challenge, encrypted handoff, callback signature, and outcome."""
    worker_port = _free_port()
    job_id, lease_id = uuid4(), uuid4()
    callback_server = CallbackCaptureServer(EXECUTOR_ID, EXECUTOR_SECRET)
    callback_server.start()
    process: subprocess.Popen[str] | None = None
    try:
        environment = os.environ.copy()
        environment.update(
            {
                "TRACKPAL_EXECUTOR_ID": str(EXECUTOR_ID),
                "TRACKPAL_EXECUTOR_SECRET": EXECUTOR_SECRET,
                "PYTHONPATH": os.pathsep.join(
                    [str(WORKER_ROOT), environment.get("PYTHONPATH", "")]
                ),
            }
        )
        process = subprocess.Popen(
            [
                "uv",
                "run",
                "--project",
                "../worker",
                "uvicorn",
                "tests.contract_app:app",
                "--port",
                str(worker_port),
            ],
            cwd=WORKER_ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        executor = _executor(worker_port)
        transport = HttpLookupExecutorTransport(resolver=LoopbackResolver())
        challenge = None
        for _ in range(50):
            try:
                challenge = await transport.challenge(executor, "contract-challenge")
                break
            except Exception:
                await asyncio.sleep(0.1)
        if challenge is None:
            assert process.poll() is None, _process_output(process)
            raise AssertionError("worker did not answer the protocol challenge")

        assert challenge.executor_id == EXECUTOR_ID
        assert challenge.protocol_version == 1
        handoff = await transport.handoff(
            executor,
            {
                "job_id": job_id,
                "lease_id": lease_id,
                "lease_expires_at": "2099-01-01T00:00:00+00:00",
                "callback_url": (
                    f"{callback_server.url}/callbacks/{job_id}/complete?trace=contract"
                ),
                "mailbox_email": "mailbox@example.com",
                "app_password": "not-used-by-fake-pipeline",
                "service_key": "netflix",
                "target_email": "customer@example.com",
                "window_minutes": 5,
            },
        )

        assert handoff.status.value == "accepted"
        assert handoff.lease_id == lease_id
        callback = callback_server.wait_for_callback()
        assert callback.path == f"/callbacks/{job_id}/complete"
        assert callback.envelope.job_id == job_id
        assert callback.envelope.lease_id == lease_id
        assert callback.envelope.outcome.kind == "found"
        assert callback.envelope.outcome.result_type == "code"
        assert callback.envelope.outcome.result_value == "654321"
        assert callback.envelope.outcome.fingerprint == "contract-fingerprint"
    finally:
        callback_server.close()
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def _process_output(process: subprocess.Popen[str]) -> str:
    stdout, stderr = process.communicate(timeout=1)
    return f"stdout={stdout}\nstderr={stderr}"
