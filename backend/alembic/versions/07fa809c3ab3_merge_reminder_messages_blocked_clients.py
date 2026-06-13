"""merge: reminder_messages + blocked_clients

Revision ID: 07fa809c3ab3
Revises: ce10fe74caa11, cf10fe74caa0
Create Date: 2026-06-11 19:38:18.036227

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "07fa809c3ab3"
down_revision: Union[str, Sequence[str], None] = ("ce10fe74caa11", "cf10fe74caa0")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
