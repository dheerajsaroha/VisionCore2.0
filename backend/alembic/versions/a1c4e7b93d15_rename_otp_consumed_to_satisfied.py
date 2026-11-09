"""name the completion marker for what it actually is

`otp_consumed_at` read as "the code was spent", and it was written on the code
path only. That left a real hole: both credentials arrive in the same message,
so resetting with the code left the reset link still valid -- a live credential
sitting in a mailbox that had already been acted on, and still usable by
anyone who copied the link first.

The row covers one reset request, and a request is satisfied by whichever
credential was presented. Renaming the column to `satisfied_at` makes that the
stated meaning, and both paths can now close the request symmetrically: the
link path consults the row before honouring a token, so a request already
completed with a code refuses the link too.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1c4e7b93d15"
down_revision: Union[str, None] = "f7b3d9c1ae42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = [c["name"] for c in insp.get_columns("password_reset_requests")]
    if "otp_consumed_at" in cols and "satisfied_at" not in cols:
        op.alter_column(
            "password_reset_requests", "otp_consumed_at",
            new_column_name="satisfied_at",
        )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = [c["name"] for c in insp.get_columns("password_reset_requests")]
    if "satisfied_at" in cols and "otp_consumed_at" not in cols:
        op.alter_column(
            "password_reset_requests", "satisfied_at",
            new_column_name="otp_consumed_at",
        )
