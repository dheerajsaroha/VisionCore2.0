"""Add renewed_at column to organization_subscriptions.

Sprint 2, Entity 2 — Subscription & Feature Management
Fix: Add missing renewed_at column used by renew_subscription() service method.

Revision ID: d4e5f6a7b8d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organization_subscriptions",
        sa.Column(
            "renewed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When subscription was last renewed",
        ),
    )
    op.create_index(
        "ix_org_subscriptions_renewed_at",
        "organization_subscriptions",
        ["renewed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_org_subscriptions_renewed_at", table_name="organization_subscriptions")
    op.drop_column("organization_subscriptions", "renewed_at")

