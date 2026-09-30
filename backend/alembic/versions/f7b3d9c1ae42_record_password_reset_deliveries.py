"""record password reset deliveries and one-time codes

A password reset that is issued, never delivered and never reported is
indistinguishable from one that worked. The endpoint answered "if that account
exists we have emailed you" while `_deliver_reset_email` returned early because
no SMTP credentials were configured, so a user could sit waiting for a message
that was never going to arrive and no log line said why.

This table makes the outcome a fact rather than an inference. One row per
request, recording:

  * what was sent and how it left (`delivery_provider`, `delivery_status`), with
    the provider's own error text, so a broken provider is diagnosable;
  * the one-time code as a *hash* with its own short expiry and attempt count,
    because 6 digits is a small space and needs tighter limits than the link;
  * `satisfied_at`, which closes the request whichever credential was used, so
    a reset completed with the code also retires the link delivered beside it.

`token_jti` ties a row back to the JWT that was minted, so a reset link and its
audit trail can be correlated without storing the token itself.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f7b3d9c1ae42"
down_revision: Union[str, None] = "d5a1b7e42c68"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "password_reset_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=True),
        sa.Column("email", sa.String(length=150), nullable=False),
        sa.Column("token_jti", sa.String(length=64), nullable=True),
        # sent | logged | skipped_unconfigured | failed. `logged` means the
        # message never left the process, which is why it is not `sent`.
        sa.Column("delivery_status", sa.String(length=30), nullable=False),
        sa.Column("delivery_provider", sa.String(length=30), nullable=True),
        sa.Column("delivery_detail", sa.String(length=500), nullable=True),
        sa.Column("delivery_error", sa.Text(), nullable=True),
        sa.Column("notified_in_app", sa.Boolean(), nullable=False,
                  server_default=sa.text("FALSE")),
        sa.Column("otp_code_hash", sa.String(length=128), nullable=True),
        sa.Column("otp_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("otp_attempts", sa.Integer(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("satisfied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"],
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    # Per-account throttling reads recent rows for one email, and the operator
    # view reads recent failures across all of them.
    op.create_index("ix_password_reset_requests_email_created",
                    "password_reset_requests", ["email", "created_at"])
    op.create_index("ix_password_reset_requests_user_id",
                    "password_reset_requests", ["user_id"])
    op.create_index("ix_password_reset_requests_delivery_status",
                    "password_reset_requests", ["delivery_status"])
    op.create_index("ix_password_reset_requests_token_jti",
                    "password_reset_requests", ["token_jti"])


def downgrade() -> None:
    op.drop_index("ix_password_reset_requests_token_jti",
                  table_name="password_reset_requests")
    op.drop_index("ix_password_reset_requests_delivery_status",
                  table_name="password_reset_requests")
    op.drop_index("ix_password_reset_requests_user_id",
                  table_name="password_reset_requests")
    op.drop_index("ix_password_reset_requests_email_created",
                  table_name="password_reset_requests")
    op.drop_table("password_reset_requests")
