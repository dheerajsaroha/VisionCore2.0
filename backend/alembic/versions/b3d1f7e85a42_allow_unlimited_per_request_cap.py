"""make_max_days_per_request_nullable

The model declares `leave_types.max_days_per_request` as `Optional[float]`, but
the column was created NOT NULL, so the two disagree and the model's intent is
unreachable.

An unlimited per-request cap cannot be expressed today. That blocks the
organization-level leave configuration: a professional-services or minimal-leave
tenant has types where no per-request limit applies, and the only way to record
that today is a large number, which then has to be special-cased everywhere.

The model already reads Optional and `leave_policy_service.evaluate_request`
already treats NULL as "unrestricted". This migration makes the column match, and
the one remaining consumer that called `float(...)` unconditionally is guarded.

Revision ID: b3d1f7e85a42
Revises: e6b4a0c2d178
Create Date: 2026-09-27 21:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b3d1f7e85a42"
down_revision: Union[str, None] = "e6b4a0c2d178"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    nullable = bind.execute(
        sa.text(
            """
            SELECT is_nullable
            FROM information_schema.columns
            WHERE table_name = 'leave_types' AND column_name = 'max_days_per_request'
            """
        )
    ).scalar()
    if nullable == "NO":
        op.alter_column(
            "leave_types",
            "max_days_per_request",
            existing_type=sa.Float(),
            nullable=True,
        )


def downgrade() -> None:
    """Restore NOT NULL.

    Rows created as explicitly unlimited would block this, so they are given a
    sentinel first. A per-request cap of 0 is treated as "unrestricted" by the
    policy evaluator, so the downgrade stays internally consistent rather than
    failing.
    """
    bind = op.get_bind()
    bind.execute(
        sa.text("UPDATE leave_types SET max_days_per_request = 0 WHERE max_days_per_request IS NULL")
    )
    op.alter_column(
        "leave_types",
        "max_days_per_request",
        existing_type=sa.Float(),
        nullable=False,
    )
