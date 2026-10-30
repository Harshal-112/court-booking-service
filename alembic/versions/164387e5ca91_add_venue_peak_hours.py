"""add venue peak hours

Revision ID: 164387e5ca91
Revises: 9058c7d039a5
Create Date: 2026-10-30 23:49:30.887621

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '164387e5ca91'
down_revision: Union[str, Sequence[str], None] = '9058c7d039a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "venues",
        sa.Column(
            "peak_start_time",
            sa.String(length=5),
            server_default="18:00",
            nullable=False,
        ),
    )

    op.add_column(
        "venues",
        sa.Column(
            "peak_end_time",
            sa.String(length=5),
            server_default="22:00",
            nullable=False,
        ),
    )

    op.create_check_constraint(
        "ck_venues_valid_peak_start_time",
        "venues",
        "peak_start_time ~ '^([01][0-9]|2[0-3]):[0-5][0-9]$'",
    )

    op.create_check_constraint(
        "ck_venues_valid_peak_end_time",
        "venues",
        "peak_end_time ~ '^([01][0-9]|2[0-3]):[0-5][0-9]$'",
    )

    op.create_check_constraint(
        "ck_venues_peak_start_before_end",
        "venues",
        "peak_start_time < peak_end_time",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_venues_peak_start_before_end",
        "venues",
        type_="check",
    )
    op.drop_constraint(
        "ck_venues_valid_peak_end_time",
        "venues",
        type_="check",
    )
    op.drop_constraint(
        "ck_venues_valid_peak_start_time",
        "venues",
        type_="check",
    )

    op.drop_column("venues", "peak_end_time")
    op.drop_column("venues", "peak_start_time")