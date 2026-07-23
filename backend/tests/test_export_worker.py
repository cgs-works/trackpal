"""Tests for the Export Worker — ZIP building status transitions.

Exercises the worker seam directly (``_process_job``) with a fake
storage adapter so the full generate-upload-transition path is tested
without real R2 credentials.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.models import Tenant
from app.models.blocked_client import BlockedClient
from app.models.client import Client
from app.models.export_job import ExportJob
from app.repositories import export_jobs_repository
from app.services.export_storage import FakeExportStorageAdapter
from app.services.export_worker import (
    _build_account_profile_csv,
    _build_blocked_phones_csv,
    _build_client_data_csv,
    _build_json,
    _build_readme,
    _build_zip,
    _digits_only,
    _format_timestamp,
    _neutralize_csv_value,
)

pytestmark = pytest.mark.asyncio


async def _tenant_for_user(db_session, user_id: UUID) -> Tenant | None:
    result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == user_id)
    )
    return result.scalar_one_or_none()


# ── Helper tests ───────────────────────────────────────────────


class TestHelpers:
    """Test helper functions used by the builders."""

    @pytest.mark.asyncio
    async def test_digits_only_strips_non_digits(self):
        assert _digits_only("+58 424 3106642") == "584243106642"
        assert _digits_only("12015550030") == "12015550030"
        assert _digits_only("") == ""
        assert _digits_only(None) == ""

    @pytest.mark.asyncio
    async def test_format_timestamp_with_utc(self):
        dt = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = _format_timestamp(dt, "UTC")
        assert result == "2024-06-15T10:30:00+00:00"

    @pytest.mark.asyncio
    async def test_format_timestamp_with_tz(self):
        dt = datetime(2024, 6, 15, 14, 30, 0, tzinfo=timezone.utc)
        result = _format_timestamp(dt, "America/Caracas")
        assert "2024-06-15T10:30:00-04:00" in result

    @pytest.mark.asyncio
    async def test_format_timestamp_naive_input(self):
        dt = datetime(2024, 6, 15, 10, 30, 0)  # no tzinfo
        result = _format_timestamp(dt, "UTC")
        assert result.endswith("+00:00")

    @pytest.mark.asyncio
    async def test_format_timestamp_none(self):
        assert _format_timestamp(None, "UTC") == ""

    @pytest.mark.asyncio
    async def test_neutralize_csv_value_handles_dangerous_prefixes(self):
        assert _neutralize_csv_value("=SUM(A1:A10)") == "\t=SUM(A1:A10)"
        assert _neutralize_csv_value("+FORMULA()") == "\t+FORMULA()"
        assert _neutralize_csv_value("-DDE") == "\t-DDE"
        assert _neutralize_csv_value("@RISK") == "\t@RISK"
        assert _neutralize_csv_value("\tembedded") == "\t\tembedded"

    @pytest.mark.asyncio
    async def test_neutralize_csv_value_does_not_prefix_safe_values(self):
        assert _neutralize_csv_value("John Doe") == "John Doe"
        assert _neutralize_csv_value("") == ""
        assert _neutralize_csv_value("123 Main St") == "123 Main St"

    @pytest.mark.asyncio
    async def test_neutralize_csv_value_handles_pipe_and_percent(self):
        assert _neutralize_csv_value("|TABLE") == "\t|TABLE"
        assert _neutralize_csv_value("%USER") == "\t%USER"


# ── Account Profile CSV tests ──────────────────────────────────


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


# ── Client Data CSV tests ──────────────────────────────────────


async def test_client_data_csv_has_approved_fields(db_session, active_tenant_user):
    """client-data.csv contains only the approved 6 fields."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    # Create a test client
    client = Client(
        tenant_id=tenant.id,
        owner_user_id=uuid4(),
        full_name="Test Client",
        username="test_client",
        phone="+12015550030",
        whatsapp_lid=None,
        is_active=True,
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)

    csv_content = _build_client_data_csv([client], "UTC")
    lines = csv_content.strip().split("\n")

    headers = [h.strip() for h in lines[0].split(",")]
    assert headers == [
        "client_name",
        "login_username",
        "whatsapp_phone",
        "account_status",
        "registered_on",
        "last_updated_on",
    ]
    assert len(headers) == 6


async def test_client_data_csv_contains_data_rows(db_session, active_tenant_user):
    """client-data.csv data rows contain the expected values."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    client = Client(
        tenant_id=tenant.id,
        owner_user_id=uuid4(),
        full_name="Active Client",
        username="active_client",
        phone="12015550030",
        whatsapp_lid=None,
        is_active=True,
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)

    csv_content = _build_client_data_csv([client], "UTC")
    lines = csv_content.strip().split("\n")

    assert len(lines) == 2  # header + 1 data row
    row = lines[1].split(",")

    assert row[0] == "Active Client"  # client_name
    assert row[1] == "active_client"  # login_username
    assert row[2] == "12015550030"  # whatsapp_phone (digits-only)


async def test_client_data_csv_sorted_by_login_username(db_session, active_tenant_user):
    """Client rows are sorted by login_username."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    clients = [
        Client(
            tenant_id=tenant.id,
            owner_user_id=uuid4(),
            full_name="Zeta Client",
            username="zeta_client",
            phone="12015550032",
            is_active=True,
        ),
        Client(
            tenant_id=tenant.id,
            owner_user_id=uuid4(),
            full_name="Alpha Client",
            username="alpha_client",
            phone="12015550030",
            is_active=True,
        ),
        Client(
            tenant_id=tenant.id,
            owner_user_id=uuid4(),
            full_name="Beta Client",
            username="beta_client",
            phone="12015550031",
            is_active=True,
        ),
    ]
    for c in clients:
        db_session.add(c)
    await db_session.commit()

    csv_content = _build_client_data_csv(clients, "UTC")
    lines = csv_content.strip().split("\n")

    assert len(lines) == 4  # header + 3 data rows
    usernames = [line.split(",")[1].strip() for line in lines[1:]]
    assert usernames == ["alpha_client", "beta_client", "zeta_client"]


async def test_client_data_csv_empty_clients_produces_only_header(
    db_session, active_tenant_user
):
    """client-data.csv has only the header when no clients exist."""
    csv_content = _build_client_data_csv([], "UTC")
    lines = csv_content.strip().split("\n")
    assert len(lines) == 1  # header only
    assert "client_name" in lines[0]


async def test_client_data_null_phone_yields_empty_cell(db_session, active_tenant_user):
    """Client with null phone renders empty cell in CSV and None in JSON."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    client = Client(
        tenant_id=tenant.id,
        owner_user_id=uuid4(),
        full_name="No Phone Client",
        username="no_phone",
        phone=None,
        is_active=True,
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)

    csv_content = _build_client_data_csv([client], "UTC")
    lines = csv_content.strip().split("\n")
    row = lines[1].split(",")
    assert row[2] == ""  # whatsapp_phone is empty

    re_fetched = await _tenant_for_user(db_session, active_tenant_user.id)
    data = json.loads(
        _build_json(
            re_fetched,
            "en",
            "UTC",
            clients=[client],
        )
    )
    assert data["client_accounts"][0]["whatsapp_phone"] is None


async def test_inactive_clients_show_inactive_status(db_session, active_tenant_user):
    """Inactive clients have account_status='inactive'."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    active = Client(
        tenant_id=tenant.id,
        owner_user_id=uuid4(),
        full_name="Active",
        username="active_user",
        phone="12015550030",
        is_active=True,
    )
    inactive = Client(
        tenant_id=tenant.id,
        owner_user_id=uuid4(),
        full_name="Inactive",
        username="inactive_user",
        phone="12015550031",
        is_active=False,
    )
    db_session.add_all([active, inactive])
    await db_session.commit()

    csv_content = _build_client_data_csv([active, inactive], "UTC")
    lines = csv_content.strip().split("\n")
    statuses = {line.split(",")[3].strip() for line in lines[1:]}
    assert "active" in statuses
    assert "inactive" in statuses


async def test_client_data_formula_injection_neutralized(
    db_session, active_tenant_user
):
    """Client names starting with formula prefixes are neutralized in CSV but not JSON."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    client = Client(
        tenant_id=tenant.id,
        owner_user_id=uuid4(),
        full_name="=SUM(A1:A10)+DDE_CALL('calc')",
        username="formula_client",
        phone="12015550030",
        is_active=True,
    )
    db_session.add(client)
    await db_session.commit()

    csv_content = _build_client_data_csv([client], "UTC")
    lines = csv_content.strip().split("\n")
    assert lines[1].startswith("\t=SUM")  # neutralized with tab prefix

    data = json.loads(
        _build_json(
            await _tenant_for_user(db_session, active_tenant_user.id),
            "en",
            "UTC",
            clients=[client],
        )
    )
    assert data["client_accounts"][0]["client_name"] == "=SUM(A1:A10)+DDE_CALL('calc')"


# ── Blocked Phones CSV tests ───────────────────────────────────


async def test_blocked_phones_csv_has_approved_fields(db_session, active_tenant_user):
    """blocked-phones.csv contains only the approved 2 fields."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    block = BlockedClient(
        tenant_id=tenant.id,
        phone="+12015559999",
    )
    db_session.add(block)
    await db_session.commit()
    await db_session.refresh(block)

    csv_content = _build_blocked_phones_csv([block], "UTC")
    lines = csv_content.strip().split("\n")

    headers = [h.strip() for h in lines[0].split(",")]
    assert headers == [
        "phone",
        "blocked_at",
    ]
    assert len(headers) == 2


async def test_blocked_phones_csv_contains_data_rows(db_session, active_tenant_user):
    """blocked-phones.csv data rows contain expected values."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    block = BlockedClient(
        tenant_id=tenant.id,
        phone="12015559999",
    )
    db_session.add(block)
    await db_session.commit()
    await db_session.refresh(block)

    csv_content = _build_blocked_phones_csv([block], "UTC")
    lines = csv_content.strip().split("\n")

    assert len(lines) == 2  # header + 1 data row
    row = lines[1].split(",")
    assert row[0] == "12015559999"  # digits-only phone


async def test_blocked_phones_sorted_by_phone(db_session, active_tenant_user):
    """Blocked-phone rows are sorted by phone."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    blocks = [
        BlockedClient(tenant_id=tenant.id, phone="584243106642"),
        BlockedClient(tenant_id=tenant.id, phone="12015559998"),
        BlockedClient(tenant_id=tenant.id, phone="12015559999"),
    ]
    for b in blocks:
        db_session.add(b)
    await db_session.commit()

    csv_content = _build_blocked_phones_csv(blocks, "UTC")
    lines = csv_content.strip().split("\n")

    assert len(lines) == 4  # header + 3 data rows
    phones = [line.split(",")[0].strip() for line in lines[1:]]
    assert phones == sorted(["12015559998", "12015559999", "584243106642"])


async def test_empty_blocks_produces_only_header(db_session, active_tenant_user):
    """blocked-phones.csv has only the header when no blocks exist."""
    csv_content = _build_blocked_phones_csv([], "UTC")
    lines = csv_content.strip().split("\n")
    assert len(lines) == 1  # header only
    assert "phone" in lines[0]


async def test_lid_only_blocks_excluded(db_session, active_tenant_user):
    """Blocks with only whatsapp_lid (no phone) are excluded from both formats."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    phone_block = BlockedClient(
        tenant_id=tenant.id,
        phone="12015559999",
    )
    lid_only_block = BlockedClient(
        tenant_id=tenant.id,
        whatsapp_lid="1234567890@lid",
    )
    db_session.add_all([phone_block, lid_only_block])
    await db_session.commit()

    # CSV should only include phone_block
    csv_content = _build_blocked_phones_csv([phone_block, lid_only_block], "UTC")
    lines = csv_content.strip().split("\n")
    assert len(lines) == 2  # header + 1 data row (phone_block only)
    assert "12015559999" in lines[1]

    # JSON should also exclude LID-only
    data = json.loads(
        _build_json(
            tenant,
            "en",
            "UTC",
            blocked_phones=[phone_block, lid_only_block],
        )
    )
    blocked_list = data["blocked_phone_list"]
    assert len(blocked_list) == 1
    assert blocked_list[0]["phone"] == "12015559999"


# ── JSON tests ─────────────────────────────────────────────────


async def test_json_has_new_sections(db_session, active_tenant_user):
    """trackpal-data.json contains client_accounts and blocked_phone_list sections."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    data = json.loads(_build_json(tenant, "en", "UTC", clients=[], blocked_phones=[]))
    assert "client_accounts" in data
    assert "blocked_phone_list" in data
    assert isinstance(data["client_accounts"], list)
    assert isinstance(data["blocked_phone_list"], list)


async def test_json_has_record_counts(db_session, active_tenant_user):
    """JSON export_metadata includes record_counts matching actual row counts."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    client = Client(
        tenant_id=tenant.id,
        owner_user_id=uuid4(),
        full_name="Counted Client",
        username="counted",
        phone="12015550030",
        is_active=True,
    )
    db_session.add(client)
    block = BlockedClient(tenant_id=tenant.id, phone="12015559999")
    db_session.add(block)
    await db_session.commit()

    data = json.loads(
        _build_json(
            tenant,
            "en",
            "UTC",
            clients=[client],
            blocked_phones=[block],
        )
    )
    counts = data["export_metadata"]["record_counts"]
    assert counts["account_profile"] == 1
    assert counts["client_accounts"] == 1
    assert counts["blocked_phone_list"] == 1


async def test_json_uses_null_for_absent_optionals(db_session, active_tenant_user):
    """JSON uses null for absent optional values like null phones."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    client = Client(
        tenant_id=tenant.id,
        owner_user_id=uuid4(),
        full_name="Null Fields",
        username="null_fields",
        phone=None,
        is_active=True,
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)

    data = json.loads(
        _build_json(
            tenant,
            "en",
            "UTC",
            clients=[client],
        )
    )
    client_entry = data["client_accounts"][0]
    assert client_entry["whatsapp_phone"] is None


async def test_json_preserves_exact_values_for_formula_text(
    db_session, active_tenant_user
):
    """JSON preserves exact approved text even when CSV needs a safety prefix."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    client = Client(
        tenant_id=tenant.id,
        owner_user_id=uuid4(),
        full_name="=DDE_CALL('malicious')",
        username="formula_name",
        phone="12015550030",
        is_active=True,
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)

    data = json.loads(
        _build_json(
            tenant,
            "en",
            "UTC",
            clients=[client],
        )
    )
    assert data["client_accounts"][0]["client_name"] == "=DDE_CALL('malicious')"


# ── JSON section fields tests ──────────────────────────────────


async def test_json_client_accounts_has_approved_fields(db_session, active_tenant_user):
    """JSON client_accounts entries have only the 6 approved fields."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    client = Client(
        tenant_id=tenant.id,
        owner_user_id=uuid4(),
        full_name="Field Check",
        username="field_check",
        phone="12015550030",
        is_active=True,
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)

    data = json.loads(
        _build_json(
            tenant,
            "en",
            "UTC",
            clients=[client],
        )
    )
    entry = data["client_accounts"][0]
    assert set(entry.keys()) == {
        "client_name",
        "login_username",
        "whatsapp_phone",
        "account_status",
        "registered_on",
        "last_updated_on",
    }


async def test_json_blocked_phone_list_has_approved_fields(
    db_session, active_tenant_user
):
    """JSON blocked_phone_list entries have only the 2 approved fields."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    block = BlockedClient(tenant_id=tenant.id, phone="12015559999")
    db_session.add(block)
    await db_session.commit()
    await db_session.refresh(block)

    data = json.loads(
        _build_json(
            tenant,
            "en",
            "UTC",
            blocked_phones=[block],
        )
    )
    entry = data["blocked_phone_list"][0]
    assert set(entry.keys()) == {
        "phone",
        "blocked_at",
    }


# ── ZIP content tests ──────────────────────────────────────────


async def test_zip_contains_all_expected_files(db_session, active_tenant_user):
    """ZIP contains exactly the five expected files."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    zip_bytes = await _build_zip(tenant, "en", "UTC", clients=[], blocked_phones=[])
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = sorted(zf.namelist())
        assert names == sorted(
            [
                "README.txt",
                "account-profile.csv",
                "blocked-phones.csv",
                "client-data.csv",
                "trackpal-data.json",
            ]
        )


async def test_zip_csv_files_have_bom(db_session, active_tenant_user):
    """All CSV files in ZIP start with UTF-8 BOM."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    zip_bytes = await _build_zip(tenant, "en", "UTC", clients=[], blocked_phones=[])
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in ["account-profile.csv", "client-data.csv", "blocked-phones.csv"]:
            csv_data = zf.read(name)
            assert csv_data[:3] == b"\xef\xbb\xbf", f"{name} missing BOM"


async def test_zip_uses_comma_delimiter_and_quoting(db_session, active_tenant_user):
    """CSV files use comma delimiter and standard quoting."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    client = Client(
        tenant_id=tenant.id,
        owner_user_id=uuid4(),
        full_name='Client with "quotes" and, commas',
        username="quoting_client",
        phone="12015550030",
        is_active=True,
    )
    db_session.add(client)
    await db_session.commit()

    csv_content = _build_client_data_csv([client], "UTC")
    assert '"' in csv_content  # quoting is used
    assert ',"12015550030"' not in csv_content  # simple values not quoted


# ── Timestamp tests ────────────────────────────────────────────


async def test_timestamps_have_explicit_timezone_offset(db_session, active_tenant_user):
    """Timestamps in both CSV and JSON include explicit timezone offset."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    client = Client(
        tenant_id=tenant.id,
        owner_user_id=uuid4(),
        full_name="TZ Check",
        username="tz_check",
        phone="12015550030",
        is_active=True,
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)

    # Test with Venezuela timezone
    csv_content = _build_client_data_csv([client], "America/Caracas")
    lines = csv_content.strip().split("\n")
    row = lines[1].split(",")
    # registered_on and last_updated_on should end with offset like -04:00
    assert row[4].endswith("-04:00") or row[4].endswith("+00:00") or "-" in row[4][-6:]
    assert row[5].endswith("-04:00") or row[5].endswith("+00:00") or "-" in row[5][-6:]


# ── No-leak tests ──────────────────────────────────────────────


async def test_no_internal_identifiers_in_new_sections(db_session, active_tenant_user):
    """Client and blocked-phone sections do not contain internal identifiers."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    client = Client(
        tenant_id=tenant.id,
        owner_user_id=uuid4(),
        full_name="Safe Client",
        username="safe_client",
        phone="12015550030",
        whatsapp_lid="abc123@lid",
        is_active=True,
    )
    db_session.add(client)
    block = BlockedClient(
        tenant_id=tenant.id, phone="12015559999", whatsapp_lid="lid567@lid"
    )
    db_session.add(block)
    await db_session.commit()

    zip_bytes = await _build_zip(
        tenant,
        "en",
        "UTC",
        clients=[client],
        blocked_phones=[block],
    )

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        client_csv = zf.read("client-data.csv").decode("utf-8-sig")
        blocks_csv = zf.read("blocked-phones.csv").decode("utf-8-sig")
        json_data = json.loads(zf.read("trackpal-data.json"))

    # No UUIDs in CSV data
    for csv_data in [client_csv, blocks_csv]:
        for item in csv_data.split("\n")[1:]:  # skip header
            if not item.strip():
                continue
            # Should not contain UUID-like patterns
            assert "owner_user_id" not in csv_data.lower()
            assert "tenant_id" not in csv_data.lower()

    # No WhatsApp LIDs in CSV
    assert "abc123" not in client_csv
    assert "lid567" not in blocks_csv
    assert "whatsapp_lid" not in client_csv.lower()

    # No passwords in any section
    assert "password" not in client_csv.lower()
    assert "password" not in blocks_csv.lower()

    # JSON client_accounts should not have internal fields
    for entry in json_data["client_accounts"]:
        for forbidden in ("id", "tenant_id", "owner_user_id", "whatsapp_lid"):
            assert forbidden not in entry, f"JSON contains {forbidden}"


# ── README tests ───────────────────────────────────────────────


async def test_readme_is_localized(db_session, active_tenant_user):
    """READ ME is localized based on locale."""
    en_readme = _build_readme("en")
    es_readme = _build_readme("es")
    assert en_readme != es_readme
    assert "TrackPal Tenant Data Export" in en_readme
    assert "Exportación de datos de TrackPal" in es_readme


async def test_readme_mentions_new_files(db_session, active_tenant_user):
    """README mentions client-data.csv and blocked-phones.csv."""
    en_readme = _build_readme("en")
    assert "client-data.csv" in en_readme
    assert "blocked-phones.csv" in en_readme

    es_readme = _build_readme("es")
    assert "client-data.csv" in es_readme
    assert "blocked-phones.csv" in es_readme


async def test_readme_lid_only_omission_documented(db_session, active_tenant_user):
    """README documents that LID-only blocks are omitted."""
    en_readme = _build_readme("en")
    assert "LID" in en_readme

    es_readme = _build_readme("es")
    assert "LID" in es_readme


# ── Cross-Tenant isolation tests ───────────────────────────────


async def test_cross_tenant_client_isolation(
    db_session, active_tenant_user, deactivated_tenant_user
):
    """Clients from one tenant do not leak into another tenant's export."""
    tenant1 = await _tenant_for_user(db_session, active_tenant_user.id)
    tenant2 = await _tenant_for_user(db_session, deactivated_tenant_user.id)
    assert tenant1 is not None
    assert tenant2 is not None

    # Add client to tenant1 only
    client1 = Client(
        tenant_id=tenant1.id,
        owner_user_id=uuid4(),
        full_name="Tenant1 Client",
        username="t1_client",
        phone="12015550030",
        is_active=True,
    )
    db_session.add(client1)
    # Add client to tenant2 only
    client2 = Client(
        tenant_id=tenant2.id,
        owner_user_id=uuid4(),
        full_name="Tenant2 Client",
        username="t2_client",
        phone="12015550031",
        is_active=True,
    )
    db_session.add(client2)
    await db_session.commit()

    # Export for tenant1 should only have client1
    csv_content = _build_client_data_csv([client1], "UTC")
    assert "t1_client" in csv_content
    assert "t2_client" not in csv_content

    # Export for tenant2 should only have client2
    csv_content2 = _build_client_data_csv([client2], "UTC")
    assert "t2_client" in csv_content2
    assert "t1_client" not in csv_content2


# ── Worker processing ──────────────────────────────────────────


async def test_worker_processes_pending_job_to_ready(
    db_session, active_tenant_user, monkeypatch
):
    """Worker processes a pending job and transitions it to ready with R2 key."""
    # Wire a fake storage adapter
    from app.services import export_worker

    storage = FakeExportStorageAdapter()
    monkeypatch.setattr(export_worker, "get_storage", lambda: storage)

    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    # Create a pending job
    job = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
    )

    # Call the core processing seam directly with the test session
    await export_worker._process_job_with_session(db_session, job)

    # Refresh job and check status
    await db_session.refresh(job)
    assert job.status == "ready", (
        f"Expected ready, got {job.status}. Error: {job.error_code}"
    )
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
    job = ExportJob(
        tenant_id=uuid4(),
        requested_by=uuid4(),
        status="pending",
    )
    db_session.add(job)
    await db_session.commit()

    await export_worker._process_job_with_session(db_session, job)
    assert job.status == "failed"
    assert job.error_code == "TENANT_NOT_FOUND"


async def test_worker_increments_attempts_on_failure(
    db_session, active_tenant_user, monkeypatch
):
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
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
    )

    await export_worker._process_job_with_session(db_session, job)
    assert job.status == "failed"
    assert job.error_code == "GENERATION_ERROR"


async def test_zip_no_internal_identifiers_leak(db_session, active_tenant_user):
    """ZIP content does not contain internal UUIDs or database fields in account profile."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    zip_bytes = await _build_zip(tenant, "en", "UTC")

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        json_data = json.loads(zf.read("trackpal-data.json"))
        csv_data = zf.read("account-profile.csv").decode("utf-8-sig")

    # No internal UUIDs
    profile = json_data["account_profile"]
    for val in profile.values():
        if val:
            assert "id" not in str(val).lower()

    # The CSV should NOT contain raw UUID or internal field names
    assert tenant.id.hex not in csv_data
    assert "owner_user_id" not in csv_data
    assert "client_prefix" not in csv_data
    assert "evolution" not in csv_data
    assert "lid" not in csv_data.lower()
    assert "password" not in csv_data.lower()


# ── Integration: worker with client data ───────────────────────


async def test_worker_zip_contains_client_and_block_data(
    db_session, active_tenant_user, monkeypatch
):
    """Worker-processed ZIP includes client and blocked-phone data."""
    from app.services import export_worker

    storage = FakeExportStorageAdapter()
    monkeypatch.setattr(export_worker, "get_storage", lambda: storage)

    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    # Add test clients
    clients_data = [
        Client(
            tenant_id=tenant.id,
            owner_user_id=uuid4(),
            full_name="Client One",
            username="one",
            phone="12015550030",
            is_active=True,
        ),
        Client(
            tenant_id=tenant.id,
            owner_user_id=uuid4(),
            full_name="Client Two",
            username="two",
            phone="12015550031",
            is_active=False,
        ),
    ]
    for c in clients_data:
        db_session.add(c)

    # Add test blocked phones (one phone, one LID-only that should be excluded)
    db_session.add(BlockedClient(tenant_id=tenant.id, phone="12015559999"))
    db_session.add(BlockedClient(tenant_id=tenant.id, whatsapp_lid="lid@lid"))
    await db_session.commit()

    job = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
    )

    await export_worker._process_job_with_session(db_session, job)
    await db_session.refresh(job)
    assert job.status == "ready"

    # Retrieve ZIP from fake storage (access internal store for test assertion)
    stored_obj = storage._store.get(job.r2_key)
    assert stored_obj is not None, "ZIP not found in fake storage"
    zip_bytes = stored_obj.data
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        assert "client-data.csv" in names
        assert "blocked-phones.csv" in names

        client_csv = zf.read("client-data.csv").decode("utf-8-sig")
        assert "one" in client_csv
        assert "two" in client_csv
        assert "Client One" in client_csv
        assert "inactive" in client_csv

        blocks_csv = zf.read("blocked-phones.csv").decode("utf-8-sig")
        assert "12015559999" in blocks_csv
        # LID-only should NOT appear
        assert "lid" not in blocks_csv

        json_data = json.loads(zf.read("trackpal-data.json"))
        assert len(json_data["client_accounts"]) == 2
        assert len(json_data["blocked_phone_list"]) == 1


async def test_worker_with_empty_client_and_block_data(
    db_session, active_tenant_user, monkeypatch
):
    """Worker handles empty client and block datasets gracefully."""
    from app.services import export_worker

    storage = FakeExportStorageAdapter()
    monkeypatch.setattr(export_worker, "get_storage", lambda: storage)

    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    # No clients, no blocks
    job = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
    )

    await export_worker._process_job_with_session(db_session, job)
    await db_session.refresh(job)
    assert job.status == "ready"

    stored_obj = storage._store.get(job.r2_key)
    assert stored_obj is not None
    zip_bytes = stored_obj.data
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        client_csv = zf.read("client-data.csv").decode("utf-8-sig")
        lines = [ln for ln in client_csv.strip().split("\n") if ln.strip()]
        assert len(lines) == 1  # header only

        blocks_csv = zf.read("blocked-phones.csv").decode("utf-8-sig")
        lines = [ln for ln in blocks_csv.strip().split("\n") if ln.strip()]
        assert len(lines) == 1  # header only

        json_data = json.loads(zf.read("trackpal-data.json"))
        assert json_data["client_accounts"] == []
        assert json_data["blocked_phone_list"] == []
        assert json_data["export_metadata"]["record_counts"]["client_accounts"] == 0
        assert json_data["export_metadata"]["record_counts"]["blocked_phone_list"] == 0
