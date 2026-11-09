"""add organization dimensions to employment records

The ORM exposes business unit, branch, and cost center properties through
EmploymentRecord, but existing databases may have created that table before
those fields were added to the model.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a3f82d9c0b61"
down_revision: Union[str, None] = "a1c4e7b93d15"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


EMPLOYMENT_DIMENSIONS = (
    ("business_unit_id", "business_units"),
    ("branch_id", "branches"),
    ("cost_center_id", "cost_centers"),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("employment_records"):
        raise RuntimeError("employment_records must exist before adding organization dimensions")

    columns = {column["name"] for column in inspector.get_columns("employment_records")}
    for column_name, referenced_table in EMPLOYMENT_DIMENSIONS:
        if not inspector.has_table(referenced_table):
            raise RuntimeError(f"{referenced_table} must exist before adding {column_name}")

        if column_name not in columns:
            op.add_column(
                "employment_records",
                sa.Column(column_name, sa.Integer(), nullable=True),
            )
            columns.add(column_name)

    foreign_keys = {
        (
            tuple(foreign_key["constrained_columns"]),
            foreign_key["referred_table"],
            tuple(foreign_key["referred_columns"]),
        )
        for foreign_key in sa.inspect(bind).get_foreign_keys("employment_records")
    }
    for column_name, referenced_table in EMPLOYMENT_DIMENSIONS:
        key = ((column_name,), referenced_table, ("id",))
        if key not in foreign_keys:
            op.create_foreign_key(
                f"fk_employment_records_{column_name}",
                "employment_records",
                referenced_table,
                [column_name],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("employment_records"):
        return

    columns = {column["name"] for column in inspector.get_columns("employment_records")}
    foreign_keys = {
        foreign_key["name"]
        for foreign_key in inspector.get_foreign_keys("employment_records")
    }
    for column_name, _ in reversed(EMPLOYMENT_DIMENSIONS):
        constraint_name = f"fk_employment_records_{column_name}"
        if constraint_name in foreign_keys:
            op.drop_constraint(constraint_name, "employment_records", type_="foreignkey")
        if column_name in columns:
            op.drop_column("employment_records", column_name)
