"""retire subscriptions category

Revision ID: 2fdc139497d5
Revises: 49c2b29272c5
Create Date: 2026-09-24 20:16:06.885103

Data only, no schema change. `Subscriptions` overlapped with the `is_subscription` flag, so it is
gone from SPEND_CATEGORIES and its rows move to the category describing what was actually bought.

Mapped by subcategory rather than by merchant, so no row can be stranded on a category that
`is_valid_pair` no longer accepts.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "2fdc139497d5"
down_revision: str | Sequence[str] | None = "49c2b29272c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# old subcategory -> (new category, new subcategory). None means the new category is flat.
MOVES: tuple[tuple[str | None, str, str | None], ...] = (
    ("Productivity", "Education", "Self Study"),
    ("Entertainment", "Leisure", "Entertainment"),
    ("Gaming", "Leisure", "Gaming"),
    (None, "Lifestyle", "Household"),
)

TABLES = ("transactions", "transaction_templates")


def upgrade() -> None:
    for table in TABLES:
        for old_subcategory, category, subcategory in MOVES:
            # IS NOT DISTINCT FROM so the NULL case matches, unlike plain =
            op.execute(
                sa.text(
                    f"UPDATE {table} SET category = :category, subcategory = :subcategory"
                    " WHERE category = 'Subscriptions'"
                    " AND subcategory IS NOT DISTINCT FROM :old_subcategory"
                ).bindparams(
                    category=category,
                    subcategory=subcategory,
                    old_subcategory=old_subcategory,
                )
            )


def downgrade() -> None:
    """Deliberately does nothing.

    The mapping is not reversible: rows that were always Leisure/Gaming are now indistinguishable
    from ones moved here, so undoing it would sweep up transactions that never belonged to
    Subscriptions. Recategorising by hand is the correct way back.
    """
