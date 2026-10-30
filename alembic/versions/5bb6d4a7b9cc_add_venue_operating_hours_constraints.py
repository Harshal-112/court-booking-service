"""add venue operating hours constraints

Revision ID: 5bb6d4a7b9cc
Revises: 2fa2b2b87b51
Create Date: 2026-10-30 23:20:49.054100

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5bb6d4a7b9cc'
down_revision: Union[str, Sequence[str], None] = '2fa2b2b87b51'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_venues_valid_opening_time",
        "venues",
        "opening_time ~ '^([01][0-9]|2[0-3]):[0-5][0-9]$'",
    )

    op.create_check_constraint(
        "ck_venues_valid_closing_time",
        "venues",
        "closing_time ~ '^([01][0-9]|2[0-3]):[0-5][0-9]$'",
    )

    op.create_check_constraint(
        "ck_venues_opening_before_closing",
        "venues",
        "opening_time < closing_time",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_venues_opening_before_closing",
        "venues",
        type_="check",
    )

    op.drop_constraint(
        "ck_venues_valid_closing_time",
        "venues",
        type_="check",
    )

    op.drop_constraint(
        "ck_venues_valid_opening_time",
        "venues",
        type_="check",
    )
