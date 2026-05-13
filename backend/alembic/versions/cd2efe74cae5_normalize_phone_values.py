"""Normalize master_profiles.phone and tenant_profiles.phone to canonical digits-only format,
dropping + prefix, JID suffixes, and non-digit characters.

Backfills existing +prefixed values to canonical digits-only format.
Raises an explicit error if normalization produces collisions within or across the two profile tables.

Revision ID: cd2efe74cae5
Revises: cd1efe74cae4
Create Date: 2026-05-12 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "cd2efe74cae5"
down_revision: Union[str, Sequence[str], None] = "cd1efe74cae4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _normalize_phone(value: str | None) -> str | None:
    """Canonicalize a phone value to digits-only without +."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    # Strip JID suffix
    if "@" in raw:
        raw = raw.split("@", 1)[0]
    # Strip device suffix
    if ":" in raw:
        raw = raw.split(":", 1)[0]
    # Keep only digits
    digits = "".join(ch for ch in raw if ch.isdigit())
    return digits if digits else None


def upgrade() -> None:
    """Backfill existing phone values to canonical digits-only format.

    Detects collisions (normalized duplicates) within each table and
    across both tables, failing with an explicit error before any writes.
    """
    conn = op.get_bind()

    # ---- Read existing values ----
    master_rows = conn.execute(
        sa.text("SELECT id, phone FROM master_profiles WHERE phone IS NOT NULL")
    ).fetchall()

    tenant_rows = conn.execute(
        sa.text("SELECT id, phone FROM tenant_profiles WHERE phone IS NOT NULL")
    ).fetchall()

    # ---- Normalize ----
    # Track ALL normalised values (including already-canonical rows) for
    # collision detection.  A row whose phone is already digits-only must
    # still be checked against rows whose stored value changes — otherwise
    # a collision where one side is already canonical would be missed.
    master_updates: list[dict] = []
    # Map canonical phone → original phone for collision error messages
    master_canonical_map: dict[str, str] = {}

    for row in master_rows:
        normalized = _normalize_phone(row.phone)
        if normalized is None:
            continue
        # Check collision against every prior row, not only updaters
        if normalized in master_canonical_map:
            raise ValueError(
                f"Collision detected in master_profiles: "
                f"phones '{master_canonical_map[normalized]}' and "
                f"'{row.phone}' both normalize to '{normalized}'. "
                f"Resolve before applying migration."
            )
        master_canonical_map[normalized] = row.phone
        if normalized != row.phone:
            master_updates.append({"id": row.id, "old_phone": row.phone, "new_phone": normalized})

    tenant_updates: list[dict] = []
    tenant_canonical_map: dict[str, str] = {}

    for row in tenant_rows:
        normalized = _normalize_phone(row.phone)
        if normalized is None:
            continue
        # Check collision against every prior row, not only updaters
        if normalized in tenant_canonical_map:
            raise ValueError(
                f"Collision detected in tenant_profiles: "
                f"phones '{tenant_canonical_map[normalized]}' and "
                f"'{row.phone}' both normalize to '{normalized}'. "
                f"Resolve before applying migration."
            )
        tenant_canonical_map[normalized] = row.phone
        if normalized != row.phone:
            tenant_updates.append({"id": row.id, "old_phone": row.phone, "new_phone": normalized})

    # ---- Cross-table collision check ----
    # Include already-canonical values in cross-table check
    master_set = set(master_canonical_map.keys())
    tenant_set = set(tenant_canonical_map.keys())
    common = master_set & tenant_set
    if common:
        collision_detail = "; ".join(
            f"'{master_canonical_map[c]}' (master) and '{tenant_canonical_map[c]}' (tenant)"
            for c in common
        )
        raise ValueError(
            f"Cross-table phone collision detected after normalization: "
            f"{collision_detail}. "
            f"Resolve before applying migration."
        )

    # ---- Apply updates ----
    for upd in master_updates:
        conn.execute(
            sa.text("UPDATE master_profiles SET phone = :new_phone WHERE id = :id"),
            {"new_phone": upd["new_phone"], "id": upd["id"]},
        )

    for upd in tenant_updates:
        conn.execute(
            sa.text("UPDATE tenant_profiles SET phone = :new_phone WHERE id = :id"),
            {"new_phone": upd["new_phone"], "id": upd["id"]},
        )


def downgrade() -> None:
    """Downgrade is a no-op: we cannot reliably restore original formats.

    The original phone formats (+prefix, JID, etc.) are not stored
    separately, so downgrade leaves canonical values in place.
    """
    pass
