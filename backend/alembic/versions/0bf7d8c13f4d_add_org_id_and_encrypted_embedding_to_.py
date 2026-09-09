"""add_org_id_and_encrypted_embedding_to_face_embeddings

Revision ID: 0bf7d8c13f4d
Revises: 14bd68687cf9
Create Date: 2026-09-09 14:00:28.014969

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0bf7d8c13f4d'
down_revision: Union[str, Sequence[str], None] = '14bd68687cf9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()

    with op.batch_alter_table("face_embeddings") as batch_op:
        batch_op.add_column(sa.Column("org_id", sa.UUID(), nullable=True))
        batch_op.add_column(sa.Column("encrypted_embedding", sa.LargeBinary(), nullable=True))
        batch_op.create_index("ix_face_embeddings_org", ["org_id"])

    conn.execute(
        sa.text(
            "UPDATE face_embeddings fe SET org_id = u.org_id FROM users u WHERE fe.user_id = u.id AND fe.org_id IS NULL"
        )
    )

    conn.commit()


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("face_embeddings") as batch_op:
        batch_op.drop_index("ix_face_embeddings_org")
        batch_op.drop_column("encrypted_embedding")
        batch_op.drop_column("org_id")
