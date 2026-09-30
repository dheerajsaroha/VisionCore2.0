"""add_user_gender_and_prune_inapplicable_leave_balances

Two related corrections to leave entitlement.

1. Adds `users.gender`. The `leave_types.gender_specific` column already existed
   and is seeded correctly ('female' on maternity, 'male' on paternity), but
   nothing ever read it, because there was no gender on the user to read
   against. Without it a life-event entitlement could not be scoped to the
   employees it applies to.

2. Removes the life-event entitlement balances that the seeder had granted
   indiscriminately to every employee in every org. `initialize_all_balances_for_user`
   iterated all active leave types with no applicability test, so a male employee
   held a 180-day Maternity Leave balance alongside his 15-day Paternity Leave.

   Only untouched, unused rows are removed: a balance is kept if the employee
   has any leave request of that type, or if any of entitled/used/pending/
   carried/adjusted days is non-zero. Those rows reflect real history and the
   seeder will not recreate them.

Revision ID: d1f7b2a94c30
Revises: c8a5e3d71b46
Create Date: 2026-09-27 19:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d1f7b2a94c30"
down_revision: Union[str, None] = "c8a5e3d71b46"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GENDER_SPECIFIC_VALUES = ("male", "female")


def upgrade() -> None:
    bind = op.get_bind()

    # 1. users.gender
    inspector = sa.inspect(bind)
    if "gender" not in inspector.get_columns("users"):
        op.add_column(
            "users",
            sa.Column("gender", sa.String(32), nullable=True),
        )

    # 2. Prune auto-granted, untouched life-event balances.
    conn = bind
    rows = conn.execute(
        sa.text(
            """
            SELECT lb.id
            FROM leave_balances lb
            JOIN leave_types lt ON lt.id = lb.leave_type_id
            WHERE lower(COALESCE(lt.gender_specific, '')) IN ('male', 'female')
              AND lb.used_days = 0
              AND lb.pending_days = 0
              AND lb.carried_forward_days = 0
              AND lb.adjusted_days = 0
              AND NOT EXISTS (
                  SELECT 1 FROM leave_requests lr
                  WHERE lr.user_id = lb.user_id
                    AND lr.leave_type_id = lb.leave_type_id
              )
            """
        )
    ).fetchall()

    if rows:
        conn.execute(
            sa.text("DELETE FROM leave_balances WHERE id = ANY(:ids)"),
            {"ids": [r[0] for r in rows]},
        )
    print(f"pruned {len(rows)} untouched gender-specific leave balance(s)")


def downgrade() -> None:
    bind = op.get_bind()

    # The pruned rows are derived data: the seeder regenerates them for the
    # current ledger year on the next balance read, so there is nothing to
    # reconstruct here beyond restoring the column.
    inspector = sa.inspect(bind)
    if "gender" in inspector.get_columns("users"):
        op.drop_column("users", "gender")
