"""oauth accounts: encrypted_oauth + nullable credentials

Revision ID: 003
Revises: 002
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "email_accounts",
        sa.Column("encrypted_oauth", sa.String(), nullable=True),
    )
    # Password ya no es obligatorio: las cuentas OAuth no tienen.
    op.alter_column(
        "email_accounts", "encrypted_credentials", existing_type=sa.String(), nullable=True
    )


def downgrade() -> None:
    op.alter_column(
        "email_accounts", "encrypted_credentials", existing_type=sa.String(), nullable=False
    )
    op.drop_column("email_accounts", "encrypted_oauth")
