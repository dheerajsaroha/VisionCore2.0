"""add_leave_templates

Leave types were a single hardcoded list injected into every tenant on first
access, so every organization received an identical six-type set including
180 days of maternity leave. What an organization offers is a business decision
that varies by sector and region, so the choice now belongs to the organization.

This adds the template tables and seeds a starting catalogue. It deliberately
does NOT touch existing `leave_types` rows: tenants that already have leave
types keep exactly what they have, and the previous seeding call is replaced by
an explicit template choice.

Revision ID: e6b4a0c2d178
Revises: d1f7b2a94c30
Create Date: 2026-09-27 20:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e6b4a0c2d178"
down_revision: Union[str, None] = "d1f7b2a94c30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "leave_templates" not in inspector.get_table_names():
        op.create_table(
            "leave_templates",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("code", sa.String(60), nullable=False),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("description", sa.String(500), nullable=True),
            sa.Column("region", sa.String(60), nullable=True),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code", name="uq_leave_templates_code"),
        )
        op.create_index("ix_leave_templates_code", "leave_templates", ["code"])
        op.create_index("ix_leave_templates_region", "leave_templates", ["region"])

    if "leave_template_items" not in inspector.get_table_names():
        op.create_table(
            "leave_template_items",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("template_id", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(40), nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("description", sa.String(300), nullable=True),
            sa.Column("max_days_per_year", sa.Float(), nullable=False, server_default=sa.text("0")),
            sa.Column("max_days_per_request", sa.Float(), nullable=True),
            sa.Column("carry_forward", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
            sa.Column("max_carry_forward_days", sa.Float(), nullable=False, server_default=sa.text("0")),
            sa.Column("requires_document", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
            sa.Column("min_notice_days", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
            sa.Column("gender_specific", sa.String(20), nullable=True),
            sa.Column("display_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["template_id"], ["leave_templates.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_leave_template_items_template_id", "leave_template_items", ["template_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "leave_template_items" in inspector.get_table_names():
        op.drop_table("leave_template_items")
    if "leave_templates" in inspector.get_table_names():
        op.drop_table("leave_templates")
