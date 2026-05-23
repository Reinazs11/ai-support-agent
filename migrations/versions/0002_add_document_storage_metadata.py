"""Add document storage metadata

Revision ID: 0002_document_storage
Revises: 0001_initial_schema
Create Date: 2026-05-23 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_document_storage"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("storage_path", sa.String(length=512), nullable=True))
    op.add_column("documents", sa.Column("size_bytes", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "size_bytes")
    op.drop_column("documents", "storage_path")
