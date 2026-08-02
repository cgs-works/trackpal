from uuid import UUID

import pytest

from app.config import ExecutorSettings


def test_executor_settings_read_required_prefixed_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRACKPAL_EXECUTOR_ID", "00000000-0000-0000-0000-000000000001")
    monkeypatch.setenv("TRACKPAL_EXECUTOR_SECRET", "executor-secret")

    settings = ExecutorSettings()

    assert settings.executor_id == UUID("00000000-0000-0000-0000-000000000001")
    assert settings.executor_secret == "executor-secret"
    assert settings.max_concurrency == 1


def test_executor_settings_reject_non_positive_concurrency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRACKPAL_EXECUTOR_ID", "00000000-0000-0000-0000-000000000001")
    monkeypatch.setenv("TRACKPAL_EXECUTOR_SECRET", "executor-secret")
    monkeypatch.setenv("TRACKPAL_MAX_CONCURRENCY", "0")

    with pytest.raises(ValueError):
        ExecutorSettings()
