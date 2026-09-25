"""add friend and rewards reimbursement sources

Revision ID: 5ca24070d25b
Revises: 2fdc139497d5
Create Date: 2026-09-24 21:04:12.118203

Hand written: autogenerate does not compare CHECK constraints, so adding a value to a StrEnum
produces no diff and `alembic check` stays quiet. Without this the new values are rejected by the
database on insert. `test_enum_values_match_the_database` guards the gap.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "5ca24070d25b"
down_revision: str | Sequence[str] | None = "2fdc139497d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT = (
    "source_valid"  # naming_convention expands this to ck_reimbursements_source_valid
)
OLD = ("Company", "Family", "Refund", "Other")
NEW = ("Company", "Family", "Friend", "Rewards", "Refund", "Other")


def _values(names: Sequence[str]) -> str:
    return ", ".join(f"'{name}'" for name in names)


def upgrade() -> None:
    op.drop_constraint(CONSTRAINT, "reimbursements", type_="check")
    op.create_check_constraint(
        "source_valid", "reimbursements", f"source IN ({_values(NEW)})"
    )


def downgrade() -> None:
    """Rows on a removed source would violate the old constraint, so move them to Other first."""
    op.execute(
        f"UPDATE reimbursements SET source = 'Other' WHERE source NOT IN ({_values(OLD)})"
    )
    op.drop_constraint(CONSTRAINT, "reimbursements", type_="check")
    op.create_check_constraint(
        "source_valid", "reimbursements", f"source IN ({_values(OLD)})"
    )
