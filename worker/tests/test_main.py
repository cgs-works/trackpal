from uuid import UUID

import pytest
from pydantic import ValidationError

from app.main import _load_production_settings


def test_production_settings_fail_fast_when_present_configuration_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRACKPAL_EXECUTOR_ID", "not-a-uuid")
    monkeypatch.setenv("TRACKPAL_EXECUTOR_SECRET", "executor-secret")

    with pytest.raises(ValidationError):
        _load_production_settings()


def test_production_settings_use_inert_configuration_when_environment_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TRACKPAL_EXECUTOR_ID", raising=False)
    monkeypatch.delenv("TRACKPAL_EXECUTOR_SECRET", raising=False)
    monkeypatch.delenv("TRACKPAL_MAX_CONCURRENCY", raising=False)

    settings = _load_production_settings()

    assert settings.executor_id == UUID(int=0)
    assert settings.executor_secret
    assert settings.max_concurrency == 1
