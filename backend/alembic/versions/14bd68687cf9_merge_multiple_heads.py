"""merge multiple heads

Revision ID: 14bd68687cf9
Revises: 3cfe8078fdb5, 531a2282e00b
Create Date: 2026-08-26 19:00:27.729470

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '14bd68687cf9'
down_revision: Union[str, Sequence[str], None] = ('3cfe8078fdb5', '531a2282e00b')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
