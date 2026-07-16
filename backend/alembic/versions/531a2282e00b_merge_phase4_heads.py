"""merge_phase4_heads

Revision ID: 531a2282e00b
Revises: 14931530a9c9, 2026_06_21_phase4_3_attendance_corrections_workflow
Create Date: 2026-06-24 22:02:10.713842

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '531a2282e00b'
down_revision: Union[str, Sequence[str], None] = ('14931530a9c9', '2026_06_21_phase4_3_attendance_corrections_workflow')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
