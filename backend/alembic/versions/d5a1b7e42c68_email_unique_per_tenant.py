"""make user email unique per tenant instead of globally

`users.email` carried a single global unique index, which quietly made the
product single-tenant in one respect: the same person could not hold an
account at two organisations, and a hiring manager in tenant B could not hire
a consultant who already had an account in tenant A. The hiring service had to
work around this by *refusing* such a hire, because the alternative -- taking
over the existing account -- would move an employee between tenants.

The unique is moved to `(org_id, lower(email))`. Case-insensitive, because
`ada@x.com` and `Ada@x.com` are one mailbox, not two employees; the index is
functional rather than a column pair so the two spellings cannot slip past it.

Emails are normalised to lowercase first. 1,006 rows carried uppercase, and
without normalising, the functional index would be enforcing a rule the stored
data did not already satisfy. Login and password reset are moved to
case-insensitive matching at the same time, so nobody is locked out by the
change -- before it, `User.email == form_data.username` was an exact match and
a user who typed their address in a different case simply failed to log in.

`users.username` stays globally unique, so username-based login remains
unambiguous and needs no disambiguation.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d5a1b7e42c68"
down_revision: Union[str, None] = "c4e8f1a93b27"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Normalise before the index is built, otherwise rows differing only by
    # case would be treated as distinct tenants-worth of one person.
    op.execute("UPDATE users SET email = lower(email) WHERE email <> lower(email)")

    # The uniqueness lived in an index, not a table constraint, so it is the
    # index that has to go. `ix_users_org_email` already covered
    # (org_id, email) but was not unique; it is replaced rather than altered so
    # the definition is written down in one place.
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_org_email", table_name="users")

    op.create_index(
        "uq_users_org_email_lower", "users", ["org_id", sa.text("lower(email)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_users_org_email_lower", table_name="users")
    op.create_index("ix_users_org_email", "users", ["org_id", "email"], unique=False)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
