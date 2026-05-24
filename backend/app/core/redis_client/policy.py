"""Circuit-breaker failover policy for Redis primary/backup."""

from __future__ import annotations

import time

from .types import FailoverState


class FailoverPolicy:
    """Encapsulates circuit-breaker rules for primary/backup Redis failover.

    Tracks consecutive primary failures.  When the configured threshold
    is reached the breaker opens and operations are routed to the backup.
    After an open window the next real-traffic operation probes the
    primary in half-open state.

    Parameters
    ----------
    failure_threshold:
        Consecutive primary failures before the breaker opens.
    open_window_seconds:
        Seconds the breaker stays open before transitioning to half-open.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        open_window_seconds: int = 30,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._open_window_seconds = open_window_seconds
        self._state = FailoverState.CLOSED
        self._consecutive_failures = 0
        self._opened_at: float | None = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> FailoverState:
        """Current state.

        This property is **read-only** — it never mutates internal
        state.  Open-window expiry is checked via
        :meth:`_check_open_window`, called explicitly from
        :meth:`~RedisConnectionManager.execute`.
        """
        return self._state

    def _check_open_window(self) -> None:
        """Transition OPEN→HALF_OPEN when the open window has elapsed.

        Called once per real-traffic operation inside :meth:`execute`
        so the state transition happens at a well-defined point rather
        than as a side-effect of reading the ``state`` property.
        """
        if self._state is FailoverState.OPEN and self._opened_at is not None:
            elapsed = time.monotonic() - self._opened_at
            if elapsed >= self._open_window_seconds:
                self._state = FailoverState.HALF_OPEN
                self._opened_at = None

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    @property
    def failure_threshold(self) -> int:
        return self._failure_threshold

    @property
    def open_window_seconds(self) -> int:
        return self._open_window_seconds

    # ------------------------------------------------------------------
    # Decision
    # ------------------------------------------------------------------

    def should_use_backup(self) -> bool:
        """``True`` when the active store should be the backup."""
        s = self.state
        return s == FailoverState.OPEN

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def record_success(self) -> None:
        """Called when a primary operation succeeds.

        Resets the consecutive-failure counter.
        If in half-open, closes the breaker.
        """
        self._consecutive_failures = 0
        if self._state is FailoverState.HALF_OPEN:
            self._state = FailoverState.CLOSED
            self._opened_at = None

    def record_failure(self) -> None:
        """Called when a primary operation fails.

        Increments the consecutive-failure counter.  If the threshold
        is met (or the breaker is half-open and fails) the breaker
        opens.
        """
        self._consecutive_failures += 1

        if self._state is FailoverState.CLOSED:
            if self._consecutive_failures >= self._failure_threshold:
                self._state = FailoverState.OPEN
                self._opened_at = time.monotonic()
        elif self._state is FailoverState.HALF_OPEN:
            self._state = FailoverState.OPEN
            self._opened_at = time.monotonic()
        # In OPEN state we keep counting failures but stay open

    def reset(self) -> None:
        """Reset to initial closed state (for testing/cleanup)."""
        self._state = FailoverState.CLOSED
        self._consecutive_failures = 0
        self._opened_at = None
