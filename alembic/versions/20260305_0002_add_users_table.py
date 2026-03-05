"""add users table

Revision ID: 20260305_0002
Revises: 20260304_0001
Create Date: 2026-03-05 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "20260305_0002"
down_revision = "20260304_0001"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    inspector = inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not _has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("username", sa.String(length=50), nullable=False),
            sa.Column("display_name", sa.String(length=100), nullable=True, server_default=""),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=True, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_users_id", "users", ["id"], unique=False)
        op.create_index("ix_users_username", "users", ["username"], unique=True)


def downgrade() -> None:
    if _has_table("users"):
        op.drop_index("ix_users_username", table_name="users")
        op.drop_index("ix_users_id", table_name="users")
        op.drop_table("users")
