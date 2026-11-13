"""fix org_api_keys is_revoked column from INTEGER to BOOLEAN

Revision ID: zz01_fix_is_revoked
Revises: a3f82d9c0b61
Branch Labels: None
Depends On: None

The original initial migration created `is_revoked` as INTEGER with a
CHECK constraint (0/1).  The SQLAlchemy model maps it as Boolean, causing
a DatatypeMismatch on INSERT.  This migration aligns the DB column type.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "zz01_fix_is_revoked"
down_revision: Union[str, Sequence[str], None] = "a3f82d9c0b61"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the check constraint that restricts values to 0/1 (integer semantics)
    op.drop_constraint("ck_api_key_revoked", "org_api_keys", type_="check")

    # Drop the partial index that uses integer comparison
    op.drop_index("ix_org_api_keys_active", table_name="org_api_keys")

    # Cast the column to BOOLEAN
    op.execute(
        "ALTER TABLE org_api_keys "
        "ALTER COLUMN is_revoked TYPE BOOLEAN "
        "USING (is_revoked::boolean)"
    )

    # Set the new server default
    op.alter_column(
        "org_api_keys",
        "is_revoked",
        server_default=sa.text("false"),
        existing_nullable=False,
    )

    # Recreate the partial index with boolean comparison
    op.create_index(
        "ix_org_api_keys_active",
        "org_api_keys",
        ["key_hash"],
        unique=False,
        postgresql_where=sa.text("is_revoked = false"),
    )


def downgrade() -> None:
    op.drop_index("ix_org_api_keys_active", table_name="org_api_keys")

    op.execute(
        "ALTER TABLE org_api_keys "
        "ALTER COLUMN is_revoked TYPE INTEGER "
        "USING (is_revoked::int)"
    )

    op.alter_column(
        "org_api_keys",
        "is_revoked",
        server_default=sa.text("0"),
        existing_nullable=False,
    )

    op.create_check_constraint(
        "ck_api_key_revoked", "org_api_keys", "is_revoked IN (0, 1)"
    )

    op.create_index(
        "ix_org_api_keys_active",
        "org_api_keys",
        ["key_hash"],
        unique=False,
        postgresql_where=sa.text("is_revoked = 0"),
    )
