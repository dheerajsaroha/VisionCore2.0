"""Add subscription and feature management models.

Sprint 2, Entity 2 — Subscription & Feature Management

Creates tables:
- subscription_plans
- organization_subscriptions
- features
- plan_features
- feature_flags
- licensing_limits

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── SubscriptionPlan ───────────────────────────────────────────────────
    op.create_table(
        "subscription_plans",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tier", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("monthly_price", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("yearly_price", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default=sa.text("'USD'")),
        sa.Column("trial_days", sa.Integer(), nullable=False, server_default=sa.text("14")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_subscription_plans_code"),
    )
    op.create_index("ix_subscription_plans_code", "subscription_plans", ["code"], unique=True)
    op.create_index("ix_subscription_plans_active", "subscription_plans", ["is_active"])
    op.create_index("ix_subscription_plans_tier", "subscription_plans", ["tier"])

    # ── OrganizationSubscription ───────────────────────────────────────────
    op.create_table(
        "organization_subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subscription_plan_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default=sa.text("'active'")),
        sa.Column("billing_cycle", sa.String(length=10), nullable=False, server_default=sa.text("'monthly'")),
        sa.Column("start_date", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_renewal", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auto_renew", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("trial_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subscription_plan_id"], ["subscription_plans.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", name="uq_org_subscription_one_per_org"),
        sa.CheckConstraint(
            "status IN ('active','trialing','canceled','expired','past_due','paused')",
            name="ck_org_subscription_status"),
        sa.CheckConstraint("billing_cycle IN ('monthly','yearly')",
                            name="ck_org_subscription_billing_cycle"),
    )
    op.create_index("ix_org_subscriptions_org", "organization_subscriptions", ["organization_id"])
    op.create_index("ix_org_subscriptions_plan", "organization_subscriptions", ["subscription_plan_id"])
    op.create_index("ix_org_subscriptions_status", "organization_subscriptions", ["status"])
    op.create_index("ix_org_subscriptions_next_renewal", "organization_subscriptions", ["next_renewal"])

    # ── Feature ────────────────────────────────────────────────────────────
    op.create_table(
        "features",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("module", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=30), nullable=False, server_default=sa.text("'core'")),
        sa.Column("dependencies", postgresql.JSONB(), nullable=True),
        sa.Column("beta", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("deprecated", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("visibility", sa.String(length=20), nullable=False, server_default=sa.text("'public'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_features_code"),
        sa.CheckConstraint(
            "visibility IN ('public','hidden','internal','admin')",
            name="ck_features_visibility"),
        sa.CheckConstraint(
            "category IN ('core','hr','finance','operations','governance',"
            "'communication','analytics','ai','platform','security')",
            name="ck_features_category"),
    )
    op.create_index("ix_features_code", "features", ["code"], unique=True)
    op.create_index("ix_features_module", "features", ["module"])
    op.create_index("ix_features_category", "features", ["category"])
    op.create_index("ix_features_deprecated", "features", ["deprecated"])

    # ── PlanFeature ────────────────────────────────────────────────────────
    op.create_table(
        "plan_features",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("feature_id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("default_on", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("configurable", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["subscription_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["feature_id"], ["features.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "feature_id", name="uq_plan_feature"),
    )
    op.create_index("ix_plan_features_plan", "plan_features", ["plan_id"])
    op.create_index("ix_plan_features_feature", "plan_features", ["feature_id"])

    # ── FeatureFlag ────────────────────────────────────────────────────────
    op.create_table(
        "feature_flags",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("feature_id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["feature_id"], ["features.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "feature_id", name="uq_org_feature_flag"),
    )
    op.create_index("ix_feature_flags_org", "feature_flags", ["organization_id"])
    op.create_index("ix_feature_flags_feature", "feature_flags", ["feature_id"])
    op.create_index("ix_feature_flags_expires", "feature_flags", ["expires_at"])

    # ── LicensingLimit ─────────────────────────────────────────────────────
    op.create_table(
        "licensing_limits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("limit_type", sa.String(length=50), nullable=False),
        sa.Column("soft_limit", sa.Integer(), nullable=True),
        sa.Column("hard_limit", sa.Integer(), nullable=True),
        sa.Column("is_unlimited", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["subscription_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "limit_type", name="uq_plan_limit_type"),
        sa.CheckConstraint(
            "NOT (is_unlimited = TRUE AND hard_limit IS NOT NULL)",
            name="ck_limit_unlimited_no_hard"),
    )
    op.create_index("ix_licensing_limits_plan", "licensing_limits", ["plan_id"])
    op.create_index("ix_licensing_limits_type", "licensing_limits", ["limit_type"])


def downgrade() -> None:
    op.drop_index("ix_licensing_limits_type", table_name="licensing_limits")
    op.drop_index("ix_licensing_limits_plan", table_name="licensing_limits")
    op.drop_table("licensing_limits")

    op.drop_index("ix_feature_flags_expires", table_name="feature_flags")
    op.drop_index("ix_feature_flags_feature", table_name="feature_flags")
    op.drop_index("ix_feature_flags_org", table_name="feature_flags")
    op.drop_table("feature_flags")

    op.drop_index("ix_plan_features_feature", table_name="plan_features")
    op.drop_index("ix_plan_features_plan", table_name="plan_features")
    op.drop_table("plan_features")

    op.drop_index("ix_features_deprecated", table_name="features")
    op.drop_index("ix_features_category", table_name="features")
    op.drop_index("ix_features_module", table_name="features")
    op.drop_index("ix_features_code", table_name="features")
    op.drop_table("features")

    op.drop_index("ix_org_subscriptions_next_renewal", table_name="organization_subscriptions")
    op.drop_index("ix_org_subscriptions_status", table_name="organization_subscriptions")
    op.drop_index("ix_org_subscriptions_plan", table_name="organization_subscriptions")
    op.drop_index("ix_org_subscriptions_org", table_name="organization_subscriptions")
    op.drop_table("organization_subscriptions")

    op.drop_index("ix_subscription_plans_tier", table_name="subscription_plans")
    op.drop_index("ix_subscription_plans_active", table_name="subscription_plans")
    op.drop_index("ix_subscription_plans_code", table_name="subscription_plans")
    op.drop_table("subscription_plans")

