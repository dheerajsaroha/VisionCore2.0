"""add_break_columns_to_attendance_logs

Revision ID: 5b9e586c6e69
Revises: 0bf7d8c13f4d
Create Date: 2026-09-09 14:09:35.607210

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5b9e586c6e69'
down_revision: Union[str, Sequence[str], None] = '0bf7d8c13f4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("attendance_logs") as batch_op:
        batch_op.add_column(sa.Column("break_start", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("break_end", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("attendance_logs") as batch_op:
        batch_op.drop_column("break_end")
        batch_op.drop_column("break_start")
