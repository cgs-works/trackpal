from __future__ import annotations

import pytest

from app import main
from app.services import export_service


def test_get_storage_fails_when_runtime_is_not_configured(monkeypatch) -> None:
    monkeypatch.setattr(export_service, "_export_storage", None)

    with pytest.raises(RuntimeError, match="Export storage is not configured"):
        export_service.get_storage()


def test_configure_export_runtime_wires_r2_and_rate_limiter(monkeypatch) -> None:
    config = object()
    storage = object()
    manager = object()
    limiter = object()
    configured: list[tuple[object, object]] = []

    monkeypatch.setattr(
        main.ExportStorageConfig,
        "from_settings",
        lambda settings: config,
    )
    monkeypatch.setattr(main, "R2ExportStorageAdapter", lambda value: storage)
    monkeypatch.setattr(main, "get_redis_manager", lambda: manager)
    monkeypatch.setattr(main, "StepUpRateLimiter", lambda value: limiter)
    monkeypatch.setattr(
        main,
        "configure_export_service",
        lambda storage_value, limiter_value: configured.append(
            (storage_value, limiter_value)
        ),
    )

    main._configure_export_runtime()

    assert configured == [(storage, limiter)]
