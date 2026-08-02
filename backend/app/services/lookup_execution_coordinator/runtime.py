"""Runtime installation of the process-wide lookup coordinator."""

from __future__ import annotations

from .coordinator import LookupExecutionCoordinator

_coordinator: LookupExecutionCoordinator | None = None


def configure_lookup_execution_coordinator(
    coordinator: LookupExecutionCoordinator | None,
) -> None:
    """Install the coordinator created during FastAPI startup."""
    global _coordinator
    _coordinator = coordinator


def get_lookup_execution_coordinator() -> LookupExecutionCoordinator:
    """Return the configured coordinator or fail closed when Redis is absent."""
    if _coordinator is None:
        raise RuntimeError("lookup execution coordination is unavailable")
    return _coordinator


__all__ = [
    "configure_lookup_execution_coordinator",
    "get_lookup_execution_coordinator",
]
