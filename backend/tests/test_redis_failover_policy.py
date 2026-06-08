"""Tests for FailoverPolicy: closed/open/half-open transitions.

Verifies threshold behavior, open window, traffic-based recovery,
success reset, and no flapping before threshold.
"""

from __future__ import annotations

import time


from app.core.redis_client import FailoverPolicy, FailoverState


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


class TestInitialState:
    def test_starts_closed(self):
        policy = FailoverPolicy()
        assert policy.state == FailoverState.CLOSED

    def test_consecutive_failures_start_at_zero(self):
        policy = FailoverPolicy()
        assert policy.consecutive_failures == 0

    def test_default_threshold(self):
        policy = FailoverPolicy()
        assert policy.failure_threshold == 3

    def test_default_open_window(self):
        policy = FailoverPolicy()
        assert policy.open_window_seconds == 30

    def test_custom_threshold_and_window(self):
        policy = FailoverPolicy(failure_threshold=5, open_window_seconds=60)
        assert policy.failure_threshold == 5
        assert policy.open_window_seconds == 60


# ---------------------------------------------------------------------------
# Closed state — success resets, failure increments
# ---------------------------------------------------------------------------


class TestClosedState:
    def test_success_resets_failure_count(self):
        policy = FailoverPolicy(failure_threshold=2)
        policy.record_failure()
        assert policy.consecutive_failures == 1
        policy.record_success()
        assert policy.consecutive_failures == 0
        assert policy.state == FailoverState.CLOSED

    def test_single_failure_below_threshold_stays_closed(self):
        policy = FailoverPolicy(failure_threshold=3)
        policy.record_failure()
        assert policy.state == FailoverState.CLOSED
        assert policy.consecutive_failures == 1

    def test_failures_below_threshold_do_not_open(self):
        policy = FailoverPolicy(failure_threshold=3)
        policy.record_failure()
        policy.record_failure()
        assert policy.state == FailoverState.CLOSED

    def test_threshold_exceeded_opens_breaker(self):
        policy = FailoverPolicy(failure_threshold=2)
        policy.record_failure()
        policy.record_failure()  # threshold reached
        assert policy.state == FailoverState.OPEN
        assert policy.consecutive_failures == 2

    def test_exactly_at_threshold_opens_breaker(self):
        policy = FailoverPolicy(failure_threshold=3)
        policy.record_failure()
        policy.record_failure()
        policy.record_failure()
        assert policy.state == FailoverState.OPEN

    def test_consecutive_failures_are_counted(self):
        policy = FailoverPolicy(failure_threshold=5)
        for _ in range(4):
            policy.record_failure()
        assert policy.consecutive_failures == 4
        assert policy.state == FailoverState.CLOSED

    def test_primary_success_after_threshold_not_yet_reached_stays_closed(self):
        """A success between failures resets count so breaker never opens."""
        policy = FailoverPolicy(failure_threshold=2)
        policy.record_failure()
        policy.record_success()
        policy.record_failure()
        assert policy.consecutive_failures == 1
        assert policy.state == FailoverState.CLOSED

    def test_failure_after_success_starts_count_anew(self):
        policy = FailoverPolicy(failure_threshold=2)
        policy.record_failure()
        policy.record_success()
        policy.record_failure()
        # One failure after the reset, not two
        assert policy.consecutive_failures == 1
        policy.record_failure()
        assert policy.state == FailoverState.OPEN


# ---------------------------------------------------------------------------
# Open state — uses backup
# ---------------------------------------------------------------------------


class TestOpenState:
    def test_open_state_active_after_threshold(self):
        policy = FailoverPolicy(failure_threshold=1)
        policy.record_failure()
        assert policy.state == FailoverState.OPEN

    def test_open_returns_backup_as_active(self):
        policy = FailoverPolicy(failure_threshold=1)
        policy.record_failure()
        assert policy.should_use_backup() is True

    def test_closed_returns_primary_as_active(self):
        policy = FailoverPolicy()
        assert policy.should_use_backup() is False

    def test_in_open_failure_count_continues_rising(self):
        policy = FailoverPolicy(failure_threshold=2)
        policy.record_failure()
        policy.record_failure()
        assert policy.state == FailoverState.OPEN
        policy.record_failure()
        assert policy.consecutive_failures == 3
        # Still open
        assert policy.state == FailoverState.OPEN

    def test_success_during_open_does_not_close(self):
        """record_success during open resets count but does not close breaker."""
        policy = FailoverPolicy(failure_threshold=2)
        policy.record_failure()
        policy.record_failure()
        assert policy.state == FailoverState.OPEN
        # record_success resets failures but breaker stays open
        # (primary hasn't been tested — only backup operated)
        policy.record_success()
        assert policy.consecutive_failures == 0
        assert policy.state == FailoverState.OPEN


# ---------------------------------------------------------------------------
# Open window and traffic-based half-open
# ---------------------------------------------------------------------------


class TestHalfOpenTransition:
    def test_open_window_not_expired_stays_open(self):
        policy = FailoverPolicy(failure_threshold=1, open_window_seconds=60)
        policy.record_failure()
        # Immediately, window not expired
        assert policy.state == FailoverState.OPEN
        assert policy.should_use_backup() is True

    def test_open_window_expired_transitions_to_half_open(self, monkeypatch):
        policy = FailoverPolicy(failure_threshold=1, open_window_seconds=0.01)
        policy.record_failure()

        # Advance time past the window
        time.sleep(0.02)

        # Transition must happen via explicit check, not as side-effect of
        # reading the ``state`` property.
        policy._check_open_window()
        assert policy.state == FailoverState.HALF_OPEN

    def test_half_open_returns_primary(self, monkeypatch):
        """In half-open, should_use_backup returns False (try primary)."""
        policy = FailoverPolicy(failure_threshold=1, open_window_seconds=0.01)
        policy.record_failure()
        time.sleep(0.02)
        policy._check_open_window()
        assert policy.state == FailoverState.HALF_OPEN
        assert policy.should_use_backup() is False

    def test_closed_does_not_transition_without_failures(self):
        """No transition when no failures occurred."""
        policy = FailoverPolicy(open_window_seconds=0.01)
        time.sleep(0.02)
        policy._check_open_window()
        assert policy.state == FailoverState.CLOSED


# ---------------------------------------------------------------------------
# Half-open success closes breaker
# ---------------------------------------------------------------------------


class TestHalfOpenSuccess:
    def test_half_open_success_closes_breaker(self, monkeypatch):
        policy = FailoverPolicy(failure_threshold=1, open_window_seconds=0.01)
        policy.record_failure()
        time.sleep(0.02)
        policy._check_open_window()
        assert policy.state == FailoverState.HALF_OPEN

        policy.record_success()
        assert policy.state == FailoverState.CLOSED
        assert policy.consecutive_failures == 0

    def test_closed_breaker_uses_primary(self):
        policy = FailoverPolicy(failure_threshold=2)
        policy.record_failure()
        policy.record_failure()
        assert policy.state == FailoverState.OPEN
        # Simulate window expired and half-open
        # Directly inject half-open state
        policy._state = FailoverState.HALF_OPEN
        policy._opened_at = None

        policy.record_success()
        assert policy.state == FailoverState.CLOSED


# ---------------------------------------------------------------------------
# Half-open failure reopens breaker
# ---------------------------------------------------------------------------


class TestHalfOpenFailure:
    def test_half_open_failure_reopens_breaker(self, monkeypatch):
        policy = FailoverPolicy(failure_threshold=1, open_window_seconds=0.01)
        policy.record_failure()
        time.sleep(0.02)
        policy._check_open_window()
        assert policy.state == FailoverState.HALF_OPEN

        policy.record_failure()
        assert policy.state == FailoverState.OPEN
        assert policy.consecutive_failures == 2

    def test_reopened_breaker_uses_backup(self):
        """After half-open failure reopens, should_use_backup returns True."""
        policy = FailoverPolicy(failure_threshold=1, open_window_seconds=60)
        policy.record_failure()
        # Directly set to half-open to avoid race with short window
        policy._state = FailoverState.HALF_OPEN
        policy._opened_at = None

        policy.record_failure()  # fails in half-open → reopens
        assert policy.should_use_backup() is True

    def test_half_open_failure_resets_timer(self, monkeypatch):
        policy = FailoverPolicy(failure_threshold=1, open_window_seconds=30)
        policy.record_failure()
        # Manually set to half-open to simulate window expired
        policy._state = FailoverState.HALF_OPEN
        policy._opened_at = time.monotonic() - 31  # would be half-open

        policy.record_failure()
        assert policy.state == FailoverState.OPEN
        # Timer was reset, so should_use_backup should be true
        assert policy.should_use_backup() is True


# ---------------------------------------------------------------------------
# No flapping before threshold
# ---------------------------------------------------------------------------


class TestNoFlapping:
    def test_no_flapping_interleaved_success_and_failure(self):
        """Success between failures prevents flapping."""
        policy = FailoverPolicy(failure_threshold=3)
        for _ in range(10):
            policy.record_failure()
            policy.record_success()
        assert policy.state == FailoverState.CLOSED
        assert policy.consecutive_failures == 0

    def test_no_flapping_single_failure_then_success(self):
        policy = FailoverPolicy(failure_threshold=3)
        policy.record_failure()
        policy.record_success()
        assert policy.state == FailoverState.CLOSED
        assert policy.consecutive_failures == 0
