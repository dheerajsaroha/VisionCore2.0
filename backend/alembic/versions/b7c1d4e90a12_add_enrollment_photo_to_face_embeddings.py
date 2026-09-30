"""add_enrollment_photo_to_face_embeddings

Stores the capture used for biometric enrollment so the identity directory and
attendance views can show whose template is on file. Served exclusively through
the authenticated, tenant-scoped `GET /users/{id}/face-photo` endpoint.

Revision ID: b7c1d4e90a12
Revises: 5b9e586c6e69
Create Date: 2026-09-27 10:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c1d4e90a12'
down_revision: Union[str, Sequence[str], None] = '5b9e586c6e69'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("face_embeddings") as batch_op:
        batch_op.add_column(sa.Column("enrollment_photo", sa.LargeBinary(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "enrollment_photo_mime",
                sa.VARCHAR(length=60),
                nullable=True,
                server_default=sa.text("'image/jpeg'"),
            )
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("face_embeddings") as batch_op:
        batch_op.drop_column("enrollment_photo_mime")
        batch_op.drop_column("enrollment_photo")
