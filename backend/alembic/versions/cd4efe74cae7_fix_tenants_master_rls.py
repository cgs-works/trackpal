"""fix tenants master rls policy

Revision ID: cd4efe74cae7
Revises: cd3efe74cae6
Create Date: 2026-05-17 17:05:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "cd4efe74cae7"
down_revision: Union[str, Sequence[str], None] = "cd3efe74cae6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenants_tenant_isolation ON tenants")
    op.execute(
        """
        CREATE POLICY tenants_tenant_isolation ON tenants
        USING (
            current_setting('app.current_role', true) = 'master'
            OR (
                current_setting('app.current_role', true) = 'tenant'
                AND owner_user_id::text = NULLIF(current_setting('app.current_user_id', true), '')
                AND is_active
            )
        )
        WITH CHECK (
            current_setting('app.current_role', true) = 'master'
            OR (
                current_setting('app.current_role', true) = 'tenant'
                AND owner_user_id::text = NULLIF(current_setting('app.current_user_id', true), '')
            )
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenants_tenant_isolation ON tenants")
    op.execute(
        """
        CREATE POLICY tenants_tenant_isolation ON tenants
        USING (
            (
                current_setting('app.current_role', true) = 'master'
                AND id::text = NULLIF(current_setting('app.active_tenant_id', true), '')
            )
            OR (
                current_setting('app.current_role', true) = 'tenant'
                AND owner_user_id::text = NULLIF(current_setting('app.current_user_id', true), '')
                AND is_active
            )
        )
        WITH CHECK (
            current_setting('app.current_role', true) = 'master'
            OR (
                current_setting('app.current_role', true) = 'tenant'
                AND owner_user_id::text = NULLIF(current_setting('app.current_user_id', true), '')
            )
        )
        """
    )
