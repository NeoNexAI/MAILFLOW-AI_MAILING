"""add organizations.api_key_hash for multi-tenant auth

Revision ID: 002
Revises: 001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("api_key_hash", sa.String(64), nullable=True),
    )
    op.create_unique_constraint(
        "uq_organizations_api_key_hash", "organizations", ["api_key_hash"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_organizations_api_key_hash", "organizations", type_="unique"
    )
    op.drop_column("organizations", "api_key_hash")
