"""add reservation member

Revision ID: b98d8f3edc2e
Revises: eb8930d3270b
Create Date: 2026-10-29 23:49:40.566901

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b98d8f3edc2e'
down_revision: Union[str, Sequence[str], None] = 'eb8930d3270b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "court_reservations",
        sa.Column("member_id", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_court_reservations_member_id",
        "court_reservations",
        ["member_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_court_reservations_member_id_members",
        "court_reservations",
        "members",
        ["member_id"],
        ["id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_court_reservations_member_id_members",
        "court_reservations",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_court_reservations_member_id",
        table_name="court_reservations",
    )
    op.drop_column("court_reservations", "member_id")

