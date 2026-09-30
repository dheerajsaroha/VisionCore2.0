"""add_offer_letter_tables

Adds the offer-letter tables behind candidate offer generation: per-tenant
templates carrying merge tags, and the generated letters themselves.

Commercial terms are stored as columns so they stay queryable and reportable,
while the rendered PDF additionally captures them as a snapshot. `expiry_date`
is derived at read time from `expires_in_days` so a candidate's response
window stays correct without a scheduled job rewriting rows.

The application runs `Base.metadata.create_all` on startup, so on any database
that has already booted with these models the tables exist outside Alembic's
version history. This migration therefore reconciles rather than blindly
creating: it creates the table when absent and only adds what is missing.

Revision ID: d8f2b70c4e19
Revises: c3a7e51d9b04
Create Date: 2026-09-27 15:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd8f2b70c4e19'
down_revision: Union[str, Sequence[str], None] = 'c3a7e51d9b04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TEMPLATE_COLUMNS = (
    ('id', sa.Integer(), True),
    ('organization_id', postgresql.UUID(as_uuid=True), False),
    ('name', sa.VARCHAR(length=120), False),
    ('subject', sa.VARCHAR(length=200), True),
    ('body', sa.Text(), False),
    ('is_default', sa.Boolean(), False),
    ('is_active', sa.Boolean(), False),
    ('created_at', sa.DateTime(timezone=True), False),
    ('updated_at', sa.DateTime(timezone=True), False),
)

LETTER_COLUMNS = (
    ('id', sa.Integer(), True),
    ('organization_id', postgresql.UUID(as_uuid=True), False),
    ('application_id', sa.Integer(), True),
    ('candidate_id', sa.Integer(), False),
    ('job_posting_id', sa.Integer(), True),
    ('template_id', sa.Integer(), True),
    ('status', sa.VARCHAR(length=30), False),
    ('designation', sa.VARCHAR(length=150), False),
    ('employment_type', sa.VARCHAR(length=50), False),
    ('location', sa.VARCHAR(length=100), True),
    ('currency', sa.VARCHAR(length=8), False),
    ('base_pay', sa.Numeric(precision=14, scale=2), False),
    ('allowances', sa.Numeric(precision=14, scale=2), False),
    ('annual_ctc', sa.Numeric(precision=14, scale=2), False),
    ('offer_date', sa.DateTime(timezone=True), False),
    ('start_date', sa.DateTime(timezone=True), False),
    ('expiry_date', sa.DateTime(timezone=True), True),
    ('expires_in_days', sa.Integer(), False),
    ('file_url', sa.Text(), True),
    ('pdf_sha256', sa.VARCHAR(length=64), True),
    ('sent_at', sa.DateTime(timezone=True), True),
    ('responded_at', sa.DateTime(timezone=True), True),
    ('decline_reason', sa.Text(), True),
    ('created_by_user_id', sa.Integer(), True),
    ('created_at', sa.DateTime(timezone=True), False),
    ('updated_at', sa.DateTime(timezone=True), False),
)

TEMPLATE_INDEXES = (
    ('ix_offer_templates_id', ['id']),
    ('ix_offer_templates_organization_id', ['organization_id']),
)

LETTER_INDEXES = (
    ('ix_offer_letters_id', ['id']),
    ('ix_offer_letters_organization_id', ['organization_id']),
    ('ix_offer_letters_application_id', ['application_id']),
    ('ix_offer_letters_candidate_id', ['candidate_id']),
    ('ix_offer_letters_job_posting_id', ['job_posting_id']),
    ('ix_offer_letters_expiry_date', ['expiry_date']),
)


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    return bool(bind.dialect.has_table(bind, table))


def _columns(table: str) -> set:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _create_missing(table: str, columns) -> None:
    existing = _columns(table)
    for name, col_type, nullable in columns:
        if name in existing:
            continue
        op.add_column(table, sa.Column(name, col_type, nullable=nullable))
        if not nullable:
            op.execute(sa.text(f'ALTER TABLE "{table}" ALTER COLUMN "{name}" SET NOT NULL'))


def _create_missing_indexes(table: str, indexes) -> None:
    present = {i["name"] for i in sa.inspect(op.get_bind()).get_indexes(table)}
    for name, columns in indexes:
        if name not in present:
            op.create_index(name, table, columns)


def upgrade() -> None:
    """Upgrade schema."""
    if not _table_exists('offer_templates'):
        op.create_table(
            'offer_templates',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('name', sa.VARCHAR(length=120), nullable=False),
            sa.Column('subject', sa.VARCHAR(length=200), nullable=True),
            sa.Column('body', sa.Text(), nullable=False),
            sa.Column('is_default', sa.Boolean(), server_default=sa.text('false'), nullable=False),
            sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
            sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('organization_id', 'name', name='uq_offer_template_org_name')
        )
    else:
        _create_missing('offer_templates', TEMPLATE_COLUMNS)
    _create_missing_indexes('offer_templates', TEMPLATE_INDEXES)

    if not _table_exists('offer_letters'):
        op.create_table(
            'offer_letters',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('application_id', sa.Integer(), nullable=True),
            sa.Column('candidate_id', sa.Integer(), nullable=False),
            sa.Column('job_posting_id', sa.Integer(), nullable=True),
            sa.Column('template_id', sa.Integer(), nullable=True),
            sa.Column('status', sa.VARCHAR(length=30), server_default=sa.text("'draft'"), nullable=False),
            sa.Column('designation', sa.VARCHAR(length=150), nullable=False),
            sa.Column('employment_type', sa.VARCHAR(length=50), server_default=sa.text("'Full-time'"), nullable=False),
            sa.Column('location', sa.VARCHAR(length=100), nullable=True),
            sa.Column('currency', sa.VARCHAR(length=8), server_default=sa.text("'USD'"), nullable=False),
            sa.Column('base_pay', sa.Numeric(precision=14, scale=2), server_default=sa.text('0'), nullable=False),
            sa.Column('allowances', sa.Numeric(precision=14, scale=2), server_default=sa.text('0'), nullable=False),
            sa.Column('annual_ctc', sa.Numeric(precision=14, scale=2), server_default=sa.text('0'), nullable=False),
            sa.Column('offer_date', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
            sa.Column('start_date', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
            sa.Column('expiry_date', sa.DateTime(timezone=True), nullable=True),
            sa.Column('expires_in_days', sa.Integer(), server_default=sa.text('7'), nullable=False),
            sa.Column('file_url', sa.Text(), nullable=True),
            sa.Column('pdf_sha256', sa.VARCHAR(length=64), nullable=True),
            sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('decline_reason', sa.Text(), nullable=True),
            sa.Column('created_by_user_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
            sa.CheckConstraint("base_pay >= 0", name='ck_offer_letter_base_non_negative'),
            sa.CheckConstraint("annual_ctc >= 0", name='ck_offer_letter_ctc_non_negative'),
            sa.CheckConstraint("expires_in_days > 0", name='ck_offer_letter_expiry_positive'),
            sa.CheckConstraint(
                "status IN ('draft','sent','accepted','declined','withdrawn','expired')",
                name='ck_offer_letter_status',
            ),
            sa.ForeignKeyConstraint(['application_id'], ['job_applications.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['job_posting_id'], ['job_postings.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['template_id'], ['offer_templates.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id')
        )
    else:
        _create_missing('offer_letters', LETTER_COLUMNS)
    _create_missing_indexes('offer_letters', LETTER_INDEXES)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('offer_letters')
    op.drop_table('offer_templates')
