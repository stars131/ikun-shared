"""add oauth accounts table

Revision ID: 20260305_0003
Revises: 20260305_0002
Create Date: 2026-03-05 00:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "20260305_0003"
down_revision = "20260305_0002"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    inspector = inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _has_index(table_name: str, index_name: str) -> bool:
    inspector = inspect(op.get_bind())
    indexes = inspector.get_indexes(table_name)
    return any(index["name"] == index_name for index in indexes)


def upgrade() -> None:
    if not _has_table("oauth_accounts"):
        op.create_table(
            "oauth_accounts",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("provider_user_id", sa.String(length=128), nullable=False),
            sa.Column("provider_username", sa.String(length=100), nullable=True, server_default=""),
            sa.Column("provider_display_name", sa.String(length=200), nullable=True, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("provider", "provider_user_id", name="uq_oauth_provider_user"),
        )

    if not _has_index("oauth_accounts", "ix_oauth_accounts_id"):
        op.create_index("ix_oauth_accounts_id", "oauth_accounts", ["id"], unique=False)
    if not _has_index("oauth_accounts", "ix_oauth_accounts_user_id"):
        op.create_index("ix_oauth_accounts_user_id", "oauth_accounts", ["user_id"], unique=False)
    if not _has_index("oauth_accounts", "ix_oauth_accounts_provider"):
        op.create_index("ix_oauth_accounts_provider", "oauth_accounts", ["provider"], unique=False)
    if not _has_index("oauth_accounts", "ix_oauth_accounts_provider_user_id"):
        op.create_index(
            "ix_oauth_accounts_provider_user_id",
            "oauth_accounts",
            ["provider_user_id"],
            unique=False,
        )
    if not _has_index("oauth_accounts", "ix_oauth_accounts_created_at"):
        op.create_index("ix_oauth_accounts_created_at", "oauth_accounts", ["created_at"], unique=False)


def downgrade() -> None:
    if _has_table("oauth_accounts"):
        op.drop_index("ix_oauth_accounts_created_at", table_name="oauth_accounts")
        op.drop_index("ix_oauth_accounts_provider_user_id", table_name="oauth_accounts")
        op.drop_index("ix_oauth_accounts_provider", table_name="oauth_accounts")
        op.drop_index("ix_oauth_accounts_user_id", table_name="oauth_accounts")
        op.drop_index("ix_oauth_accounts_id", table_name="oauth_accounts")
        op.drop_table("oauth_accounts")
