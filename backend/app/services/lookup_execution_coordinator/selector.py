"""Pure executor capacity selection for external lookup dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ExecutorCapacity:
    """Capacity snapshot used to choose one dispatchable executor."""

    executor_id: UUID
    active_leases: int
    max_concurrency: int
    last_selected_at: datetime | None = None


def select_executor(
    candidates: list[ExecutorCapacity],
) -> ExecutorCapacity | None:
    """Return the least-loaded executor with deterministic tie-breaking."""
    eligible = [
        item
        for item in candidates
        if item.max_concurrency > 0 and item.active_leases < item.max_concurrency
    ]
    return min(
        eligible,
        key=lambda item: (
            item.active_leases / item.max_concurrency,
            item.last_selected_at or datetime.min.replace(tzinfo=timezone.utc),
            str(item.executor_id),
        ),
        default=None,
    )


__all__ = ["ExecutorCapacity", "select_executor"]
