"""Deterministic worker application used by the backend contract test."""

from __future__ import annotations

from app.config import ExecutorSettings
from app.main import create_app
from app.pipeline.models import LookupCommand, LookupOutcome
from app.runtime import ExecutorRuntime


async def fake_pipeline(command: LookupCommand) -> LookupOutcome:
    """Return a stable result without connecting to a mailbox provider."""
    del command
    return LookupOutcome.found(
        result_type="code",
        result_value="654321",
        message_id="contract-message",
        fingerprint="contract-fingerprint",
    )


settings = ExecutorSettings()
runtime = ExecutorRuntime(settings, pipeline=fake_pipeline)
app = create_app(settings, runtime)

__all__ = ["app", "create_app"]
