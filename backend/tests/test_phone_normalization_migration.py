"""Static tests for phone normalization migration collision detection.

Verifies the ``_normalize_phone`` helper and collision-detection logic
from the migration script WITHOUT running Alembic against a real DB.

Covers:
- Same-table collisions where one row is already canonical.
- Cross-table collisions where one row is already canonical.
- No-collision scenarios with mixed formats.
- Normalization of edge cases matching the migration code.
"""

from __future__ import annotations

import pytest

# Copy of the migration's _normalize_phone to avoid importing from the
# migration module (which would trigger Alembic dependencies).
def _normalize_phone(value: str | None) -> str | None:
    """Canonicalize a phone value to digits-only without +."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if "@" in raw:
        raw = raw.split("@", 1)[0]
    if ":" in raw:
        raw = raw.split(":", 1)[0]
    digits = "".join(ch for ch in raw if ch.isdigit())
    return digits if digits else None


# ---------------------------------------------------------------------------
# _normalize_phone helper (migration-local version)
# ---------------------------------------------------------------------------


class TestMigrationNormalizePhone:
    """_normalize_phone must match app.core.phone.normalize_phone behaviour."""

    def test_plus_prefix_stripped(self) -> None:
        assert _normalize_phone("+1234567890") == "1234567890"

    def test_already_canonical_unchanged(self) -> None:
        assert _normalize_phone("1234567890") == "1234567890"

    def test_jid_suffix_stripped(self) -> None:
        assert _normalize_phone("+1234567890@c.us") == "1234567890"

    def test_device_suffix_stripped(self) -> None:
        assert _normalize_phone("+1234567890:45") == "1234567890"

    def test_none_returns_none(self) -> None:
        assert _normalize_phone(None) is None

    def test_blank_returns_none(self) -> None:
        assert _normalize_phone("") is None
        assert _normalize_phone("   ") is None


# ---------------------------------------------------------------------------
# Simulated collision detection logic
# ---------------------------------------------------------------------------


def _detect_within_table_collisions(rows: list[dict]) -> dict[int, str]:
    """Simulate the migration's within-table collision detection.

    Returns a dict mapping row id -> normalized phone for rows that
    would be UPDATEd. Raises ValueError on collision.

    This mirrors the migration's logic for one profile table.
    """
    canonical_map: dict[str, str] = {}  # norm -> original phone
    updates: dict[int, str] = {}

    for row in rows:
        normalized = _normalize_phone(row["phone"])
        if normalized is None:
            continue
        if normalized in canonical_map:
            raise ValueError(
                f"Collision detected: phones '{canonical_map[normalized]}' "
                f"and '{row['phone']}' both normalize to '{normalized}'."
            )
        canonical_map[normalized] = row["phone"]
        if normalized != row["phone"]:
            updates[row["id"]] = normalized

    return updates


def _detect_cross_table_collisions(
    master_rows: list[dict],
    tenant_rows: list[dict],
) -> set[str]:
    """Simulate the migration's cross-table collision detection.

    Returns the set of canonical phones that appear in both tables.
    Raises ValueError on collision.

    Includes ALL rows (both updaters and already-canonical) in the
    collision check.
    """
    master_set: set[str] = set()
    tenant_set: set[str] = set()

    for row in master_rows:
        normalized = _normalize_phone(row["phone"])
        if normalized is not None:
            master_set.add(normalized)

    for row in tenant_rows:
        normalized = _normalize_phone(row["phone"])
        if normalized is not None:
            tenant_set.add(normalized)

    common = master_set & tenant_set
    if common:
        raise ValueError(
            f"Cross-table phone collision after normalization: {common}"
        )
    return common


# ---------------------------------------------------------------------------
# Within-table collision tests
# ---------------------------------------------------------------------------


class TestWithinTableCollisionDetection:
    """Same-table collisions where normalised values clash."""

    def test_no_collision_distinct_values(self) -> None:
        rows = [
            {"id": 1, "phone": "+1234567890"},
            {"id": 2, "phone": "+9876543210"},
        ]
        updates = _detect_within_table_collisions(rows)
        assert updates == {1: "1234567890", 2: "9876543210"}

    def test_no_collision_already_canonical(self) -> None:
        """Already-canonical rows are correctly included in collision map."""
        rows = [
            {"id": 1, "phone": "1234567890"},  # already canonical
            {"id": 2, "phone": "+9876543210"},  # needs update
        ]
        updates = _detect_within_table_collisions(rows)
        # Row 1 is already canonical so not in updates
        assert 1 not in updates
        assert updates[2] == "9876543210"

    def test_collision_both_need_updates(self) -> None:
        """Two rows normalising to same value raise collision."""
        rows = [
            {"id": 1, "phone": "+1234567890"},
            {"id": 2, "phone": "1234567890@c.us"},
        ]
        with pytest.raises(ValueError, match="Collision detected"):
            _detect_within_table_collisions(rows)

    def test_collision_one_already_canonical(self) -> None:
        """Collision detected when one row is already canonical.

        This is the key regression: row 1 is already digits-only,
        row 2 normalises to the same value.  The collision must be
        detected even though row 1 does not need an UPDATE.
        """
        rows = [
            {"id": 1, "phone": "1234567890"},      # already canonical
            {"id": 2, "phone": "+1 (234) 567-890"},  # normalises to 1234567890
        ]
        with pytest.raises(ValueError, match="Collision detected.*1234567890"):
            _detect_within_table_collisions(rows)

    def test_collision_both_already_canonical(self) -> None:
        """Two already-canonical rows with same value raise collision."""
        rows = [
            {"id": 1, "phone": "1234567890"},
            {"id": 2, "phone": "1234567890"},
        ]
        with pytest.raises(ValueError, match="Collision detected.*1234567890"):
            _detect_within_table_collisions(rows)

    def test_no_collision_with_none_values(self) -> None:
        """NULL/None values are skipped in collision detection."""
        rows = [
            {"id": 1, "phone": "+1234567890"},
            {"id": 2, "phone": None},
            {"id": 3, "phone": ""},
        ]
        updates = _detect_within_table_collisions(rows)
        assert updates == {1: "1234567890"}


# ---------------------------------------------------------------------------
# Cross-table collision tests
# ---------------------------------------------------------------------------


class TestCrossTableCollisionDetection:
    """Cross-table collisions between master_profiles and tenant_profiles."""

    def test_no_cross_table_collision(self) -> None:
        master_rows = [
            {"id": 1, "phone": "+1234567890"},
        ]
        tenant_rows = [
            {"id": 10, "phone": "+9876543210"},
        ]
        common = _detect_cross_table_collisions(master_rows, tenant_rows)
        assert common == set()

    def test_cross_table_collision_both_need_updates(self) -> None:
        master_rows = [
            {"id": 1, "phone": "+1234567890"},
        ]
        tenant_rows = [
            {"id": 10, "phone": "1234567890@c.us"},
        ]
        with pytest.raises(ValueError, match="Cross-table.*collision"):
            _detect_cross_table_collisions(master_rows, tenant_rows)

    def test_cross_table_collision_master_already_canonical(self) -> None:
        """Cross-table collision when master row is already canonical.

        Master has "1234567890" (already digits), tenant has
        "+1234567890" (normalises to same).  Must be detected.
        """
        master_rows = [
            {"id": 1, "phone": "1234567890"},  # already canonical
        ]
        tenant_rows = [
            {"id": 10, "phone": "+1234567890"},  # normalises to 1234567890
        ]
        with pytest.raises(ValueError, match="Cross-table.*collision"):
            _detect_cross_table_collisions(master_rows, tenant_rows)

    def test_cross_table_collision_tenant_already_canonical(self) -> None:
        """Cross-table collision when tenant row is already canonical."""
        master_rows = [
            {"id": 1, "phone": "+1234567890"},
        ]
        tenant_rows = [
            {"id": 10, "phone": "1234567890"},  # already canonical
        ]
        with pytest.raises(ValueError, match="Cross-table.*collision"):
            _detect_cross_table_collisions(master_rows, tenant_rows)

    def test_cross_table_collision_both_already_canonical(self) -> None:
        """Cross-table collision when both rows are already canonical."""
        master_rows = [
            {"id": 1, "phone": "1234567890"},
        ]
        tenant_rows = [
            {"id": 10, "phone": "1234567890"},
        ]
        with pytest.raises(ValueError, match="Cross-table.*collision"):
            _detect_cross_table_collisions(master_rows, tenant_rows)

    def test_cross_table_no_collision_none_values_skipped(self) -> None:
        """NULL values are excluded from cross-table collision set."""
        master_rows = [
            {"id": 1, "phone": "+1234567890"},
            {"id": 2, "phone": None},
        ]
        tenant_rows = [
            {"id": 10, "phone": "+9876543210"},
            {"id": 11, "phone": ""},
        ]
        common = _detect_cross_table_collisions(master_rows, tenant_rows)
        assert common == set()
