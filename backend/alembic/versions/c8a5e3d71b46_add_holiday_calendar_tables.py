"""add_holiday_calendar_tables

Brings `holiday_calendars` and `holiday_entries` into migration history.

Both tables were only ever created by `Base.metadata.create_all` during
application startup, so they were absent from the managed schema. A deployment
that provisions with `alembic upgrade head` (as `scripts/deploy.sh` does) had no
holiday calendar at all, and no migration could create one.

The migration is written to match the models exactly, including the
`holiday_type` CHECK constraint, so the table is identical whether it arrives
via Alembic or `create_all`.

Revision ID: c8a5e3d71b46
Revises: b1d4f8a06c23
Create Date: 2026-09-27 18:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c8a5e3d71b46'
down_revision: Union[str, Sequence[str], None] = 'b1d4f8a06c23'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


HOLIDAY_TYPES = "'NATIONAL','OPTIONAL','RESTRICTED','ORG_SPECIFIC'"


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()

    if not bind.dialect.has_table(bind, 'holiday_calendars'):
        op.create_table(
            'holiday_calendars',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('name', sa.VARCHAR(length=150), nullable=False),
            # Region/state scope, so a tenant can be matched to the right
            # pre-configured public holiday calendar.
            sa.Column('country_code', sa.VARCHAR(length=3), nullable=True),
            sa.Column('region', sa.VARCHAR(length=100), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('is_default', sa.Boolean(), nullable=False,
                      server_default=sa.text('FALSE')),
            sa.Column('is_active', sa.Boolean(), nullable=False,
                      server_default=sa.text('TRUE')),
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('NOW()')),
            sa.Column('updated_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('NOW()')),
            sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('org_id', 'name', name='uq_holiday_calendar_org_name'),
        )
        op.create_index('ix_holiday_calendars_id', 'holiday_calendars', ['id'])
        op.create_index('ix_holiday_calendars_org_id', 'holiday_calendars', ['org_id'])

    if not bind.dialect.has_table(bind, 'holiday_entries'):
        op.create_table(
            'holiday_entries',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('calendar_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.VARCHAR(length=200), nullable=False),
            sa.Column('holiday_date', sa.Date(), nullable=False),
            sa.Column('holiday_type', sa.VARCHAR(length=20), nullable=False),
            sa.Column('is_recurring', sa.Boolean(), nullable=False,
                      server_default=sa.text('TRUE')),
            sa.Column('year', sa.Integer(), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('NOW()')),
            sa.CheckConstraint(
                f"holiday_type::text = ANY (ARRAY[{HOLIDAY_TYPES}])",
                name='ck_holiday_entry_type',
            ),
            sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['calendar_id'], ['holiday_calendars.id'],
                                    ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_holiday_entries_id', 'holiday_entries', ['id'])
        op.create_index('ix_holiday_entries_org_id', 'holiday_entries', ['org_id'])
        op.create_index('ix_holiday_entries_calendar_id', 'holiday_entries',
                        ['calendar_id'])


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if bind.dialect.has_table(bind, 'holiday_entries'):
        op.drop_table('holiday_entries')
    if bind.dialect.has_table(bind, 'holiday_calendars'):
        op.drop_table('holiday_calendars')
