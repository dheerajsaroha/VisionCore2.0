"""close the recruitment-to-employment loop

Recruitment and Core & Identity kept two unrelated notions of a "position",
and nothing connected the moment a candidate was marked hired. `stage` became
the string 'hired' and that was the entire effect: no user account, no
employment record, and no slot consumed, so approving a hire left the org
structure exactly as it was.

This adds the four links that let a vacancy mean a slot:

  * `job_postings.position_id`  -- which internal slot this advert fills. One
    column is enough to relate two features that shared only a name.
  * `job_postings.headcount`    -- how many openings the advert covers. Without
    it a posting is implicitly single-hire and `headcount_capacity` can never
    be exceeded, so the capacity check would be unfalsifiable.
  * `employee_invites.position_id` -- carries that slot through onboarding,
    which is the only place the User row is actually created.
  * `job_applications.hired_employment_id` -- the idempotency key. The
    employment record is created synchronously at hire time, so this is what
    stops a repeated PATCH from minting a second hire and a second invite.

All four are nullable, so existing rows are untouched and a tenant that never
links its postings to positions keeps working; those hires simply record no
slot.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c4e8f1a93b27"
down_revision: Union[str, None] = "f2a91c7be304"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "job_postings",
        sa.Column("position_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_job_postings_position_id", "job_postings", "job_positions",
        ["position_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_job_postings_position_id", "job_postings", ["position_id"])

    op.add_column(
        "job_postings",
        sa.Column("headcount", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_check_constraint(
        "ck_job_postings_headcount_positive", "job_postings", "headcount >= 1",
    )

    op.add_column(
        "employee_invites",
        sa.Column("position_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_employee_invites_position_id", "employee_invites", "job_positions",
        ["position_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_employee_invites_position_id", "employee_invites", ["position_id"])

    op.add_column(
        "job_applications",
        sa.Column("hired_employment_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_job_applications_hired_employment_id", "job_applications",
        "employment_records", ["hired_employment_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index(
        "ix_job_applications_hired_employment_id", "job_applications",
        ["hired_employment_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_job_applications_hired_employment_id", table_name="job_applications")
    op.drop_constraint("fk_job_applications_hired_employment_id", "job_applications",
                       type_="foreignkey")
    op.drop_column("job_applications", "hired_employment_id")

    op.drop_index("ix_employee_invites_position_id", table_name="employee_invites")
    op.drop_constraint("fk_employee_invites_position_id", "employee_invites",
                       type_="foreignkey")
    op.drop_column("employee_invites", "position_id")

    op.drop_constraint("ck_job_postings_headcount_positive", "job_postings",
                       type_="check")
    op.drop_column("job_postings", "headcount")

    op.drop_index("ix_job_postings_position_id", table_name="job_postings")
    op.drop_constraint("fk_job_postings_position_id", "job_postings",
                       type_="foreignkey")
    op.drop_column("job_postings", "position_id")
