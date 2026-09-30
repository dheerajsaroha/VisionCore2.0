"""reconcile_salary_structures_effective_dating

`f0087438a3dc` created `salary_structures` without `effective_from`,
`effective_to` or `is_active`, but `payroll_engine._get_salary_structure`
filters on all three. Because `scripts/deploy.sh` provisions with
`alembic upgrade head` and `create_all` never ALTERs an existing table, a
freshly migrated database made every payroll run fail with
`UndefinedColumn`. This migration reconciles the table with the model.

It also drops the unique index on `user_id` alone. That index makes a
mid-year raise impossible: a second structure row cannot be inserted, so an
increase overwrites history and re-running a closed month recomputes it at the
new rate. Uniqueness moves to `(user_id, effective_from)`, which still blocks
duplicate effective dates while allowing successive versions.

Revision ID: f4c7a2b91e60
Revises: e6a1d84f2c37
Create Date: 2026-09-27 17:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f4c7a2b91e60'
down_revision: Union[str, Sequence[str], None] = 'e6a1d84f2c37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE = 'salary_structures'

# (name, type, server_default)
COLUMNS = (
    ('effective_from', sa.DateTime(timezone=True), None),
    ('effective_to', sa.DateTime(timezone=True), None),
    ('is_active', sa.Boolean(), sa.text('true')),
)


def _columns() -> set:
    bind = op.get_bind()
    return {c['name'] for c in sa.inspect(bind).get_columns(TABLE)}


def _index_names() -> set:
    bind = op.get_bind()
    names = {i['name'] for i in sa.inspect(bind).get_indexes(TABLE)}
    for u in sa.inspect(bind).get_unique_constraints(TABLE):
        names.add(u['name'])
    return names


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, TABLE):
        return

    existing = _columns()
    for name, col_type, default in COLUMNS:
        if name in existing:
            continue
        op.add_column(TABLE, sa.Column(name, col_type, nullable=True, server_default=default))

    # A NULL effective_from means "always in effect", so the engine's
    # effective-dating filter must treat NULL as open-ended. Backfill existing
    # rows to a concrete date so existing structures keep being found.
    op.execute(sa.text(
        f'UPDATE "{TABLE}" SET effective_from = updated_at '
        f"WHERE effective_from IS NULL AND updated_at IS NOT NULL"
    ))

    # Replace single-column uniqueness with per-effective-date uniqueness so
    # successive salary versions can coexist.
    for name in _index_names():
        if 'user_id' in name and name.endswith('user_id'):
            op.drop_index(name, table_name=TABLE)

    indexes = sa.inspect(bind).get_indexes(TABLE)
    if not any(i.get('unique') and i['column_names'] == ['user_id', 'effective_from']
               for i in indexes):
        op.create_index(
            'uq_salary_structures_user_effective',
            TABLE,
            ['user_id', 'effective_from'],
            unique=True,
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, TABLE):
        return

    indexes = sa.inspect(bind).get_indexes(TABLE)
    if any(i['name'] == 'uq_salary_structures_user_effective' for i in indexes):
        op.drop_index('uq_salary_structures_user_effective', table_name=TABLE)

    # Keep only the newest version per user, then restore the old constraint.
    op.execute(sa.text(f'''
        DELETE FROM "{TABLE}" a
        USING "{TABLE}" b
        WHERE a.user_id = b.user_id
          AND (a.effective_from, a.id) < (b.effective_from, b.id)
    '''))
    if not any(i.get('unique') and i['column_names'] == ['user_id']
               for i in sa.inspect(bind).get_indexes(TABLE)):
        op.create_index('ix_salary_structures_user_id', TABLE, ['user_id'], unique=True)
