"""Add RBAC columns to roles table (description, tier, is_system, created_at)

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to roles table (IF NOT EXISTS — idempotent)
    op.execute("ALTER TABLE roles ADD COLUMN IF NOT EXISTS description TEXT")
    op.execute(
        "ALTER TABLE roles ADD COLUMN IF NOT EXISTS tier VARCHAR(20) "
        "NOT NULL DEFAULT 'organization'"
    )
    op.execute(
        "ALTER TABLE roles ADD COLUMN IF NOT EXISTS is_system BOOLEAN "
        "NOT NULL DEFAULT FALSE"
    )
    op.execute(
        "ALTER TABLE roles ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ "
        "NOT NULL DEFAULT NOW()"
    )

    # Create indexes (IF NOT EXISTS via safe execution)
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)

    # Check if ix_roles_tier exists
    existing_indexes = [idx["name"] for idx in inspector.get_indexes("roles")]
    if "ix_roles_tier" not in existing_indexes:
        op.create_index("ix_roles_tier", "roles", ["tier"], unique=False)

    # Add unique constraint on roles.name if it doesn't exist
    existing_constraints = [c["name"] for c in inspector.get_unique_constraints("roles")]
    if "uq_roles_name" not in existing_constraints:
        op.create_unique_constraint("uq_roles_name", "roles", ["name"])

    # Create tables if they don't exist (IF NOT EXISTS)
    if "permissions" not in inspector.get_table_names():
        op.create_table(
            "permissions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False, unique=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("module", sa.String(length=50), nullable=False,
                       server_default=sa.text("'general'")),
            sa.Column("group", sa.String(length=50), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False,
                       server_default=sa.text("TRUE")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                       server_default=sa.text("NOW()")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name", name="uq_permissions_name"),
        )
        op.create_index("ix_permissions_module", "permissions", ["module"], unique=False)
        op.create_index("ix_permissions_group", "permissions", ["group"], unique=False)

    if "role_permissions" not in inspector.get_table_names():
        op.create_table(
            "role_permissions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("role_id", sa.Integer(), nullable=False),
            sa.Column("permission_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                       server_default=sa.text("NOW()")),
            sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
        )
        op.create_index("ix_role_permissions_role_id", "role_permissions", ["role_id"], unique=False)
        op.create_index("ix_role_permissions_permission_id", "role_permissions", ["permission_id"], unique=False)

    if "system_settings" not in inspector.get_table_names():
        op.create_table(
            "system_settings",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("key", sa.String(length=100), nullable=False, unique=True),
            sa.Column("value", sa.Text(), nullable=False),
            sa.Column("category", sa.String(length=50), nullable=True,
                       server_default=sa.text("'general'")),
            sa.Column("is_encrypted", sa.Boolean(), nullable=False,
                       server_default=sa.text("FALSE")),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                       server_default=sa.text("NOW()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                       server_default=sa.text("NOW()")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("key", name="uq_system_settings_key"),
        )
        op.create_index("ix_system_settings_category", "system_settings", ["category"], unique=False)


def downgrade() -> None:
    # Drop tables
    op.drop_table("system_settings")
    op.drop_table("role_permissions")
    op.drop_table("permissions")

    # Drop constraints and indexes
    op.drop_constraint("uq_roles_name", "roles", type_="unique")
    op.drop_index("ix_roles_tier", table_name="roles")

    # Drop columns
    op.drop_column("roles", "created_at")
    op.drop_column("roles", "is_system")
    op.drop_column("roles", "tier")
    op.drop_column("roles", "description")

