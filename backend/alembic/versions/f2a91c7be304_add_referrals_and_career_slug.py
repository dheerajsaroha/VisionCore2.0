"""add_referrals_and_career_slug

Adds employee referrals and a public careers page.

Two things were missing for a referral programme to exist at all:

  * there was no `referrals` table. `referral_program` was seeded as a feature
    gate and `referral.verify` as a permission, but nothing could ever create
    or read a referral, so the entitlement bought nothing.
  * there was no public way to reach an organization's vacancies. Every
    recruitment route required an authenticated session, so a job posted by an
    organization could only be seen by that organization's own staff -- it
    could not be shown on their careers page or website.

`organizations.career_slug` is the public identifier for that page. It is
nullable and deliberately not backfilled: generating a slug for thousands of
existing tenants in one migration would take a unique index over every row for
no benefit, since the value is only needed when an org first publishes a
careers page.

Revision ID: f2a91c7be304
Revises: b3d1f7e85a42
Create Date: 2026-09-27 22:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f2a91c7be304"
down_revision: Union[str, None] = "b3d1f7e85a42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("career_slug", sa.String(length=80), nullable=True),
    )
    op.create_index(
        "ix_organizations_career_slug", "organizations", ["career_slug"],
        unique=True, postgresql_where=sa.text("career_slug IS NOT NULL"),
    )

    op.create_table(
        "referrals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  nullable=False),
        sa.Column("job_posting_id", sa.Integer(), nullable=True),
        sa.Column("referrer_user_id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=True),
        sa.Column("referred_name", sa.String(length=100), nullable=False),
        sa.Column("referred_email", sa.String(length=150), nullable=False),
        sa.Column("referred_phone", sa.String(length=30), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("referral_code", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False,
                  server_default=sa.text("'pending'")),
        sa.Column("reward_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("reward_status", sa.String(length=20), nullable=True),
        sa.Column("verified_by_user_id", sa.Integer(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_posting_id"], ["job_postings.id"],
                                ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["referrer_user_id"], ["users.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"],
                                ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["verified_by_user_id"], ["users.id"],
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_referrals_id", "referrals", ["id"], unique=False)
    op.create_index("ix_referrals_organization_id", "referrals",
                    ["organization_id"], unique=False)
    op.create_index("ix_referrals_job_posting_id", "referrals",
                    ["job_posting_id"], unique=False)
    op.create_index("ix_referrals_referrer_user_id", "referrals",
                    ["referrer_user_id"], unique=False)
    op.create_index("ix_referrals_candidate_id", "referrals",
                    ["candidate_id"], unique=False)
    op.create_index("ix_referrals_referred_email", "referrals",
                    ["referred_email"], unique=False)
    op.create_index("ix_referrals_referral_code", "referrals",
                    ["referral_code"], unique=True)
    # The same person cannot be referred twice for the same vacancy by the
    # same employee. Partial index so general referrals (no vacancy) stay legal.
    op.create_index(
        "ux_referral_referrer_email_job", "referrals",
        ["referrer_user_id", "referred_email", "job_posting_id"],
        unique=True, postgresql_where=sa.text("job_posting_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ux_referral_referrer_email_job", table_name="referrals")
    op.drop_index("ix_referrals_referral_code", table_name="referrals")
    op.drop_index("ix_referrals_referred_email", table_name="referrals")
    op.drop_index("ix_referrals_candidate_id", table_name="referrals")
    op.drop_index("ix_referrals_referrer_user_id", table_name="referrals")
    op.drop_index("ix_referrals_job_posting_id", table_name="referrals")
    op.drop_index("ix_referrals_organization_id", table_name="referrals")
    op.drop_index("ix_referrals_id", table_name="referrals")
    op.drop_table("referrals")
    op.drop_index("ix_organizations_career_slug", table_name="organizations")
    op.drop_column("organizations", "career_slug")
