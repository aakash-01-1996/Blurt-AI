"""add transcript source_language

Revision ID: c5e1a2f7b3d8
Revises: b4df3b8aee10
Create Date: 2026-11-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5e1a2f7b3d8"
down_revision: str | None = "b4df3b8aee10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transcripts",
        sa.Column("source_language", sa.String(length=16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("transcripts", "source_language")
