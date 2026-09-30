"""add_employee_invites_table

Adds the onboarding invite table behind magic-link employee onboarding.

Invites are database-backed rather than JWTs so an organisation can revoke a
link and audit who was invited, for as long as the employee record exists. The
raw token is stored only as a SHA-256 hash, so a database leak cannot be
replayed into working onboarding links.

The onboarding checklist timestamps live here rather than in a separate table
because they describe the invitation's journey, not reusable data.

Revision ID: e6a1d84f2c37
Revises: d8f2b70c4e19
Create Date: 2026-09-27 16:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e6a1d84f2c37'
down_revision: Union[str, Sequence[str], None] = 'd8f2b70c4e19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COLUMNS = (
    ('id', sa.Integer(), False),
    ('organization_id', postgresql.UUID(as_uuid=True), False),
    ('email', sa.VARCHAR(length=150), False),
    ('full_name', sa.VARCHAR(length=100), True),
    ('token_hash', sa.VARCHAR(length=64), False),
    ('role_id', sa.Integer(), False),
    ('department_id', sa.Integer(), True),
    ('manager_id', sa.Integer(), True),
    ('status', sa.VARCHAR(length=20), False),
    ('expires_at', sa.DateTime(timezone=True), False),
    ('used_at', sa.DateTime(timezone=True), True),
    ('revoked_at', sa.DateTime(timezone=True), True),
    ('profile_completed_at', sa.DateTime(timezone=True), True),
    ('documents_completed_at', sa.DateTime(timezone=True), True),
    ('tax_form_completed_at', sa.DateTime(timezone=True), True),
    ('accepted_user_id', sa.Integer(), True),
    ('invited_by_user_id', sa.Integer(), True),
    ('created_at', sa.DateTime(timezone=True), False),
)

INDEXES = (
    ('ix_employee_invites_id', ['id']),
    ('ix_employee_invites_organization_id', ['organization_id']),
    ('ix_employee_invites_email', ['email']),
    ('ix_employee_invites_token_hash', ['token_hash']),
    ('ix_employee_invites_role_id', ['role_id']),
    ('ix_employee_invites_department_id', ['department_id']),
    ('ix_employee_invites_invited_by_user_id', ['invited_by_user_id']),
    ('ix_employee_invites_expires_at', ['expires_at']),
)


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    return bool(bind.dialect.has_table(bind, table))


def upgrade() -> None:
    """Upgrade schema."""
    if not _table_exists('employee_invites'):
        op.create_table(
            'employee_invites',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('email', sa.VARCHAR(length=150), nullable=False),
            sa.Column('full_name', sa.VARCHAR(length=100), nullable=True),
            sa.Column('token_hash', sa.VARCHAR(length=64), nullable=False),
            sa.Column('role_id', sa.Integer(), nullable=False),
            sa.Column('department_id', sa.Integer(), nullable=True),
            sa.Column('manager_id', sa.Integer(), nullable=True),
            sa.Column('status', sa.VARCHAR(length=20), server_default=sa.text("'pending'"), nullable=False),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('profile_completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('documents_completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('tax_form_completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('accepted_user_id', sa.Integer(), nullable=True),
            sa.Column('invited_by_user_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
            sa.CheckConstraint("status IN ('pending','accepted','revoked')",
                               name='ck_employee_invite_status'),
            sa.ForeignKeyConstraint(['accepted_user_id'], ['users.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['invited_by_user_id'], ['users.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['manager_id'], ['users.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='RESTRICT'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('token_hash')
        )
    else:
        # The application runs create_all on startup, so the table may already
        # exist outside Alembic's history; add only what is missing.
        existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns('employee_invites')}
        for name, col_type, nullable in COLUMNS:
            if name in existing:
                continue
            op.add_column('employee_invites', sa.Column(name, col_type, nullable=nullable))
            if not nullable:
                op.execute(sa.text(
                    f'ALTER TABLE "employee_invites" ALTER COLUMN "{name}" SET NOT NULL'
                ))

    present = {i["name"] for i in sa.inspect(op.get_bind()).get_indexes('employee_invites')}
    for name, columns in INDEXES:
        if name not in present:
            op.create_index(name, 'employee_invites', columns)

    # Partial index backing the "one live invite per address" lookup: it covers
    # only rows that could still be accepted, so it stays small as history grows.
    if 'ix_employee_invite_active' not in present:
        op.create_index(
            'ix_employee_invite_active',
            'employee_invites',
            ['organization_id'],
            postgresql_where=sa.text("status = 'pending' AND used_at IS NULL"),
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_employee_invite_active', table_name='employee_invites')
    op.drop_table('employee_invites')
