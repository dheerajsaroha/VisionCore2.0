"""Add branding fields to Organization

Revision ID: a1a75b402e6e
Revises: 3eaaee4c0cc5
Create Date: 2026-07-18 10:56:33.114090

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1a75b402e6e'
down_revision: Union[str, Sequence[str], None] = '3eaaee4c0cc5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Sanitized upgrade: only adds the intended new columns.
    The original autogenerate was destructive (incorrectly detected existing
    tables as needing to be dropped). This version only performs additive changes.
    """
    # Add branding columns to organizations table (IF NOT EXISTS is safe to re-run)
    op.execute("ALTER TABLE organizations ADD COLUMN IF NOT EXISTS logo_url VARCHAR(512)")
    op.execute("ALTER TABLE organizations ADD COLUMN IF NOT EXISTS primary_color VARCHAR(7) NOT NULL DEFAULT '#4F46E5'")



def downgrade() -> None:
    """Reverse the additive changes only."""
    op.execute("ALTER TABLE organizations DROP COLUMN IF EXISTS primary_color")
    op.execute("ALTER TABLE organizations DROP COLUMN IF EXISTS logo_url")
