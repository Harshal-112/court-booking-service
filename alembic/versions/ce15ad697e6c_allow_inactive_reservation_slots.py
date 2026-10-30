"""allow inactive reservation slots

Revision ID: ce15ad697e6c
Revises: b98d8f3edc2e
Create Date: 2026-10-29 23:58:09.619221

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ce15ad697e6c'
down_revision: Union[str, Sequence[str], None] = 'b98d8f3edc2e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Remove the old exclusion constraint.
    op.execute("""
        ALTER TABLE court_reservations
        DROP CONSTRAINT ex_court_reservations_no_overlap
    """)

    # Permit expired as an additional reservation status.
    op.create_check_constraint(
        "ck_court_reservations_valid_status",
        "court_reservations",
        "status IN ('held', 'confirmed', 'cancelled', 'expired')",
    )

    # Prevent overlapping slots only for active reservations.
    op.execute("""
        ALTER TABLE court_reservations
        ADD CONSTRAINT ex_court_reservations_no_overlap
        EXCLUDE USING gist (
            court_id WITH =,
            (tstzrange(starts_at, ends_at, '[)')) WITH &&
        )
        WHERE (status IN ('held', 'confirmed'))
    """)


def downgrade() -> None:
    """Downgrade schema."""

    # Remove the partial exclusion constraint.
    op.execute("""
        ALTER TABLE court_reservations
        DROP CONSTRAINT ex_court_reservations_no_overlap
    """)

    op.drop_constraint(
        "ck_court_reservations_valid_status",
        "court_reservations",
        type_="check",
    )

    # Restore the original exclusion constraint.
    op.execute("""
        ALTER TABLE court_reservations
        ADD CONSTRAINT ex_court_reservations_no_overlap
        EXCLUDE USING gist (
            court_id WITH =,
            (tstzrange(starts_at, ends_at, '[)')) WITH &&
        )
    """)