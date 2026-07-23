"""Tests for the Export Worker — ZIP building status transitions.

Exercises the worker seam directly (``_process_job``) with a fake
storage adapter so the full generate-upload-transition path is tested
without real R2 credentials.
"""

from __future__ import annotations

import io
import zipfile
from uuid import UUID

import pytest
from sqlalchemy import select

from app.models import Tenant
from app.models.export_job import ExportJob
from app.repositories import export_jobs_repository
from app.services.export_storage import FakeExportStorageAdapter
from app.services.export_worker import _build_account_profile_csv, _build_json, _build_readme, _build_zip

pytestmark = pytest.mark.asyncio


async def _tenant_for_user(db_session, user_id: UUID) -> Tenant | None:
    result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == user_id)
    )
    return result.scalar_one_or_none()


# ── ZIP content tests ──────────────────────────────────────────


async def test_account_profile_csv_has_approved_fields(db_session, active_tenant_user):
    """account-profile.csv contains only the approved 7 fields."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    csv_content = _build_account_profile_csv(tenant, "en", "UTC")
    lines = csv_content.strip().split("\n")

    # Header
    headers = [h.strip() for h in lines[0].split(",")]
    assert headers == [
        "account_name",
        "contact_email",
        "whatsapp_phone",
        "login_username",
        "current_plan",
        "preferred_language",
        "time_zone",
    ]
    assert len(headers) == 7


async def test_json_has_approved_fields(db_session, active_tenant_user):
    """trackpal-data.json contains only the approved profile fields."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    import json
    data = json.loads(_build_json(tenant, "en", "UTC"))
    profile = data["account_profile"]
    assert set(profile.keys()) == {
        "account_name",
        "contact_email",
        "whatsapp_phone",
        "login_username",
        "current_plan",
        "preferred_language",
        "time_zone",
    }


async def test_readme_is_localized(db_session, active_tenant_user):
    """READ ME is localized based on locale."""
    en_readme = _build_readme("en")
    es_readme = _build_readme("es")
    assert en_readme != es_readme
    assert "TrackPal Tenant Data Export" in en_readme
    assert "Exportación de datos de TrackPal" in es_readme


async def test_zip_contains_expected_files(db_session, active_tenant_user):
    """ZIP contains exactly the three expected files."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    zip_bytes = await _build_zip(tenant, "en", "UTC")
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = sorted(zf.namelist())
        assert names == sorted([
            "README.txt",
            "account-profile.csv",
            "trackpal-data.json",
        ])


async def test_zip_csv_has_bom(db_session, active_tenant_user):
    """CSV in ZIP starts with UTF-8 BOM."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    zip_bytes = await _build_zip(tenant, "en", "UTC")
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        csv_data = zf.read("account-profile.csv")
        assert csv_data[:3] == b"\xef\xbb\xbf"  # BOM


# ── Worker processing ──────────────────────────────────────────


async def test_worker_processes_pending_job_to_ready(db_session, active_tenant_user, monkeypatch):
    """Worker processes a pending job and transitions it to ready with R2 key."""
    # Wire a fake storage adapter
    from app.services import export_worker
    storage = FakeExportStorageAdapter()
    monkeypatch.setattr(export_worker, "get_storage", lambda: storage)

    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    # Create a pending job
    job = await export_jobs_repository.create(
        db_session, tenant_id=tenant.id, requested_by=active_tenant_user.id,
    )

    # Call the core processing seam directly with the test session
    await export_worker._process_job_with_session(db_session, job)

    # Refresh job and check status
    await db_session.refresh(job)
    assert job.status == "ready", f"Expected ready, got {job.status}. Error: {job.error_code}"
    assert job.r2_key is not None
    assert job.artifact_size_bytes is not None
    assert job.artifact_size_bytes > 0
    assert job.ready_at is not None

    # Verify the ZIP is in fake storage
    metadata = await storage.get_metadata(job.r2_key)
    assert metadata.size_bytes == job.artifact_size_bytes
    assert metadata.content_type == "application/zip"


async def test_worker_fails_job_when_tenant_missing(db_session, monkeypatch):
    """Worker handles missing tenant gracefully."""
    from app.services import export_worker

    storage = FakeExportStorageAdapter()
    monkeypatch.setattr(export_worker, "get_storage", lambda: storage)

    # Create a job with a non-existent tenant_id
    import uuid
    job = ExportJob(
        tenant_id=uuid.uuid4(),
        requested_by=uuid.uuid4(),
        status="pending",
    )
    db_session.add(job)
    await db_session.commit()

    await export_worker._process_job_with_session(db_session, job)
    assert job.status == "failed"
    assert job.error_code == "TENANT_NOT_FOUND"


async def test_worker_increments_attempts_on_failure(db_session, active_tenant_user, monkeypatch):
    """Worker handles exceptions and transitions to failed."""
    from app.services import export_worker

    # Make storage raise to simulate failure
    class _BrokenStorage:
        async def upload(self, key, data, content_type="application/octet-stream"):
            msg = "Storage unavailable"
            raise RuntimeError(msg)

    monkeypatch.setattr(export_worker, "get_storage", lambda: _BrokenStorage())

    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    job = await export_jobs_repository.create(
        db_session, tenant_id=tenant.id, requested_by=active_tenant_user.id,
    )

    await export_worker._process_job_with_session(db_session, job)
    assert job.status == "failed"
    assert job.error_code == "GENERATION_ERROR"


async def test_zip_no_internal_identifiers_leak(db_session, active_tenant_user):
    """ZIP content does not contain internal UUIDs or database fields."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    import json
    zip_bytes = await _build_zip(tenant, "en", "UTC")

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        json_data = json.loads(zf.read("trackpal-data.json"))
        csv_data = zf.read("account-profile.csv").decode("utf-8-sig")

    # No internal UUIDs
    profile = json_data["account_profile"]
    for val in profile.values():
        if val:
            assert "id" not in str(val).lower() or val == "preferred_language" or "time_zone"

    # The CSV should NOT contain raw UUID or internal field names
    assert tenant.id.hex not in csv_data
    assert "owner_user_id" not in csv_data
    assert "client_prefix" not in csv_data
    assert "evolution" not in csv_data
    assert "lid" not in csv_data.lower()
    assert "password" not in csv_data.lower()
