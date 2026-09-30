"""add_payroll_currency

Snapshots the ISO 4217 currency a payroll was computed in onto the payroll row.

`payslip_service.resolve_currency` had no tenant-specific source and always
returned USD, while the statutory engine deducts INR amounts. A payslip is a
legal document, so it must be labelled with the currency its own figures are
denominated in. Existing rows are backfilled to the statutory engine's default
(INR), which is what their deductions were actually computed in.

Revision ID: b1d4f8a06c23
Revises: f4c7a2b91e60
Create Date: 2026-09-27 18:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b1d4f8a06c23'
down_revision: Union[str, Sequence[str], None] = 'f4c7a2b91e60'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE = 'payrolls'


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, TABLE):
        return

    columns = {c['name'] for c in sa.inspect(bind).get_columns(TABLE)}
    if 'currency' not in columns:
        op.add_column(
            TABLE,
            sa.Column('currency', sa.VARCHAR(length=3), nullable=False,
                      server_default=sa.text("'INR'")),
        )

    # Rows created before this migration were computed by the India statutory
    # engine, so INR is the truthful backfill rather than the old USD default.
    op.execute(sa.text(
        f'UPDATE "{TABLE}" SET currency = \'INR\' WHERE currency IS NULL'
    ))


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, TABLE):
        return
    columns = {c['name'] for c in sa.inspect(bind).get_columns(TABLE)}
    if 'currency' in columns:
        op.drop_column(TABLE, 'currency')
