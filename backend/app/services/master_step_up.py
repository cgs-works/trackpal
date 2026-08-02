"""Shared fail-closed Master password step-up authentication."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.models import User
from app.services.step_up_limiter import (
    StepUpError,
    StepUpRateLimiter,
    StepUpRedisError,
)


@dataclass(frozen=True)
class MasterStepUpError(Exception):
    """Stable service error raised when Master step-up cannot succeed."""

    code: str
    status_code: int

    def __str__(self) -> str:
        return self.code


async def verify_master_step_up(
    db: AsyncSession,
    master_user: User,
    password: str,
    limiter: StepUpRateLimiter | None,
) -> None:
    """Verify a Master password through the shared fail-closed limiter.

    ``db`` is part of the service contract so callers can use this helper at
    the database boundary; the already-authenticated user is the source of
    the password hash.
    """
    del db
    if limiter is None:
        raise MasterStepUpError("step_up_unavailable", 503)

    actor_id = str(master_user.id)
    try:
        await limiter.check(actor_id)
    except StepUpError as exc:
        code = (
            "step_up_unavailable"
            if isinstance(exc, StepUpRedisError)
            else "step_up_rate_limited"
        )
        status_code = 503 if code == "step_up_unavailable" else 429
        raise MasterStepUpError(code, status_code) from exc

    if not verify_password(password, master_user.password_hash):
        try:
            await limiter.record_failure(actor_id)
        except StepUpError as exc:
            raise MasterStepUpError("step_up_unavailable", 503) from exc
        raise MasterStepUpError("invalid_master_password", 401)

    try:
        await limiter.record_success(actor_id)
    except StepUpError:
        # The limiter's success path is intentionally best effort. The
        # password was valid and the next check remains fail-closed.
        pass


__all__ = ["MasterStepUpError", "verify_master_step_up"]
