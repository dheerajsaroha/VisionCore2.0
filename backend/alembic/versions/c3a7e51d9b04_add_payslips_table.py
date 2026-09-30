"""add_payslips_table

Maps and upgrades the `payslips` table that backs generated PDF payslips.

Context: the payroll router already queried a `Payslip` model, but no such
model was ever defined, so `GET /payroll/{id}/payslip` failed with an
ImportError on every call. An untracked `payslips` table did exist, created
outside Alembic by an early metadata create_all, with a narrower legacy shape
(`document_url`, no org, no monetary snapshot) and no Alembic revision.

This reconciles both cases: on a database that still has the legacy table the
columns are altered in place and existing rows backfilled; on a fresh database
the table is created directly. Monetary columns hold an immutable snapshot of
the figures rendered into the PDF so a payslip stays auditable if the payroll
row is later recalculated.

Revision ID: c3a7e51d9b04
Revises: b7c1d4e90a12
Create Date: 2026-09-27 11:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c3a7e51d9b04'
down_revision: Union[str, Sequence[str], None] = 'b7c1d4e90a12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists() -> bool:
    bind = op.get_bind()
    return bool(bind.dialect.has_table(bind, "payslips"))


def _columns() -> set:
    inspector = sa.inspect(op.get_bind())
    return {c["name"] for c in inspector.get_columns("payslips")}


def _index_exists(name: str) -> bool:
    bind = op.get_bind()
    return any(i["name"] == name for i in sa.inspect(bind).get_indexes("payslips"))


def _create_index(name: str, columns: list) -> None:
    # The legacy table already carries some of these, so creation must be
    # tolerant of a partially indexed pre-existing table.
    if not _index_exists(name):
        op.create_index(name, 'payslips', columns)


def _fk_exists(name: str) -> bool:
    bind = op.get_bind()
    return any(c["name"] == name for c in sa.inspect(bind).get_foreign_keys("payslips"))


def _create_fk(name: str, target: str, local: list, remote: list, ondelete: str) -> None:
    if not _fk_exists(name):
        op.create_foreign_key(name, 'payslips', target, local, remote, ondelete=ondelete)


def _constraint_exists(name: str) -> bool:
    bind = op.get_bind()
    return any(c["name"] == name for c in sa.inspect(bind).get_check_constraints("payslips")) or any(
        u["name"] == name for u in sa.inspect(bind).get_unique_constraints("payslips")
    )


def _create_unique(name: str, columns: list) -> None:
    # One payslip per payroll row keeps regeneration idempotent.
    if not _constraint_exists(name):
        op.create_unique_constraint(name, 'payslips', columns)


def _create_check(name: str, condition: str) -> None:
    if not _constraint_exists(name):
        op.create_check_constraint(name, 'payslips', condition)


def upgrade() -> None:
    """Upgrade schema."""
    legacy = _table_exists()

    if not legacy:
        op.create_table(
            'payslips',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('payroll_id', sa.Integer(), nullable=False),
            sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('file_url', sa.Text(), nullable=False),
            sa.Column('pdf_sha256', sa.VARCHAR(length=64), nullable=True),
            sa.Column('period_label', sa.VARCHAR(length=20), nullable=True),
            sa.Column('currency', sa.VARCHAR(length=8), nullable=False, server_default=sa.text("'USD'")),
            sa.Column('gross_salary', sa.Numeric(precision=14, scale=2), nullable=False, server_default=sa.text('0')),
            sa.Column('total_deductions', sa.Numeric(precision=14, scale=2), nullable=False, server_default=sa.text('0')),
            sa.Column('net_pay', sa.Numeric(precision=14, scale=2), nullable=False, server_default=sa.text('0')),
            sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
            sa.Column('generated_by_user_id', sa.Integer(), nullable=True),
            sa.CheckConstraint('gross_salary >= 0', name='ck_payslip_gross_non_negative'),
            sa.CheckConstraint('total_deductions >= 0', name='ck_payslip_deductions_non_negative'),
            sa.ForeignKeyConstraint(['generated_by_user_id'], ['users.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['payroll_id'], ['payrolls.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('payroll_id', name='uq_payslip_payroll')
        )
    else:
        existing = _columns()

        # Legacy column renamed rather than dropped so stored paths survive.
        if 'document_url' in existing and 'file_url' not in existing:
            op.alter_column('payslips', 'document_url', new_column_name='file_url',
                            existing_type=sa.String(), existing_nullable=False)
            # Re-read: the rename happened outside the cached column set.
            existing = _columns()
        if 'file_url' not in existing:
            op.add_column('payslips', sa.Column('file_url', sa.Text(), nullable=True))

        op.add_column('payslips', sa.Column('pdf_sha256', sa.VARCHAR(length=64), nullable=True))
        op.add_column('payslips', sa.Column('period_label', sa.VARCHAR(length=20), nullable=True))
        op.add_column('payslips', sa.Column('currency', sa.VARCHAR(length=8), nullable=False,
                                            server_default=sa.text("'USD'")))
        op.add_column('payslips', sa.Column('gross_salary', sa.Numeric(precision=14, scale=2), nullable=False,
                                            server_default=sa.text('0')))
        op.add_column('payslips', sa.Column('total_deductions', sa.Numeric(precision=14, scale=2), nullable=False,
                                            server_default=sa.text('0')))
        op.add_column('payslips', sa.Column('net_pay', sa.Numeric(precision=14, scale=2), nullable=False,
                                            server_default=sa.text('0')))
        op.add_column('payslips', sa.Column('generated_by_user_id', sa.Integer(), nullable=True))
        # Added nullable first so the legacy rows can be backfilled before the
        # NOT NULL constraint is applied.
        op.add_column('payslips', sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=True))

        # Legacy rows carry no tenant of their own; inherit it from the payroll.
        op.execute(
            """
            UPDATE payslips p
               SET org_id = pr.org_id,
                   period_label = to_char(make_date(pr.year, pr.month, 1), 'YYYY-MM'),
                   gross_salary = pr.base_salary,
                   total_deductions = pr.deductions,
                   net_pay = pr.total_salary
              FROM payrolls pr
             WHERE pr.id = p.payroll_id
            """
        )
        op.alter_column('payslips', 'org_id', nullable=False)
        op.alter_column('payslips', 'file_url', nullable=False,
                        existing_type=sa.Text())

        _create_fk('fk_payslips_org_id', 'organizations', ['org_id'], ['id'], 'CASCADE')
        _create_fk('fk_payslips_generated_by', 'users', ['generated_by_user_id'], ['id'], 'SET NULL')

    _create_unique('uq_payslip_payroll', ['payroll_id'])
    _create_check('ck_payslip_gross_non_negative', 'gross_salary >= 0')
    _create_check('ck_payslip_deductions_non_negative', 'total_deductions >= 0')

    _create_index('ix_payslips_id', ['id'])
    _create_index('ix_payslips_payroll_id', ['payroll_id'])
    _create_index('ix_payslips_org_id', ['org_id'])
    _create_index('ix_payslips_user_id', ['user_id'])
    _create_index('ix_payslips_period_label', ['period_label'])


def downgrade() -> None:
    """Downgrade schema."""
    for index in ('ix_payslips_period_label', 'ix_payslips_user_id', 'ix_payslips_org_id',
                  'ix_payslips_payroll_id', 'ix_payslips_id'):
        if _index_exists(index):
            op.drop_index(index, table_name='payslips')
    op.drop_table('payslips')
