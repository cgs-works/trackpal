"""Redis connection types, exceptions, and infrastructure error detection."""

from __future__ import annotations

import enum


class RedisUnavailableError(RuntimeError):
    """Raised when Redis is unavailable after exhausting failover.

    Wraps low-level ``ConnectionError``, ``TimeoutError``,
    ``OSError``, and ``redis.RedisError`` so callers can handle
    Redis infrastructure failures with a single domain exception.
    Configuration errors (e.g. no primary URL) remain plain
    ``RuntimeError``.
    """

    pass


class FailoverState(enum.Enum):
    """Circuit-breaker state for Redis active-passive failover.

    States
    ------
    CLOSED:
        Primary Redis is active. Operations go to primary.
    OPEN:
        Backup Redis is active after consecutive primary failures.
    HALF_OPEN:
        Open window expired; next real operation will probe primary.
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


#: Exception types indicating a Redis infrastructure failure
#: (as opposed to application-level bugs in the callable).
REDIS_INFRA_ERRORS: tuple[type[Exception], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,
)


def is_redis_infra_error(exc: Exception) -> bool:
    """Return True when *exc* signals a Redis infrastructure failure.

    Matches both built-in socket-level exceptions (``ConnectionError``,
    ``TimeoutError``, ``OSError``) and redis-py-specific exceptions
    (``redis.exceptions.ConnectionError``, etc.).  Application-level
    bugs like ``AttributeError``, ``TypeError`` and ``ValueError`` are
    excluded and propagate as-is.
    """
    if isinstance(exc, REDIS_INFRA_ERRORS):
        return True
    module = type(exc).__module__
    return module.startswith("redis.")
