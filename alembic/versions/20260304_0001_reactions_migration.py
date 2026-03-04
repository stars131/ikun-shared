"""add reactions columns and table

Revision ID: 20260304_0001
Revises:
Create Date: 2026-03-04 01:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "20260304_0001"
down_revision = None
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    inspector = inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _has_index(table_name: str, index_name: str) -> bool:
    inspector = inspect(op.get_bind())
    indexes = inspector.get_indexes(table_name)
    return any(index["name"] == index_name for index in indexes)


def upgrade() -> None:
    if not _has_table("resources"):
        op.create_table(
            "resources",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("category", sa.String(length=50), nullable=False),
            sa.Column("tags", sa.String(length=255), nullable=True),
            sa.Column("author", sa.String(length=100), nullable=True),
            sa.Column("external_url", sa.String(length=500), nullable=True),
            sa.Column("file_path", sa.String(length=500), nullable=True),
            sa.Column("preview_image", sa.String(length=500), nullable=True),
            sa.Column("downloads", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("likes", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("favorites", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_resources_id", "resources", ["id"], unique=False)
        op.create_index("ix_resources_title", "resources", ["title"], unique=False)
        op.create_index("ix_resources_category", "resources", ["category"], unique=False)
        op.create_index("ix_resources_created_at", "resources", ["created_at"], unique=False)
    else:
        if not _has_column("resources", "likes"):
            op.add_column(
                "resources",
                sa.Column("likes", sa.Integer(), nullable=False, server_default="0"),
            )
        if not _has_column("resources", "favorites"):
            op.add_column(
                "resources",
                sa.Column("favorites", sa.Integer(), nullable=False, server_default="0"),
            )

    if not _has_table("resource_reactions"):
        op.create_table(
            "resource_reactions",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("resource_id", sa.Integer(), nullable=False),
            sa.Column("client_token", sa.String(length=64), nullable=False),
            sa.Column("action", sa.String(length=20), nullable=False),
            sa.Column("day_key", sa.String(length=10), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="CASCADE"),
            sa.UniqueConstraint(
                "resource_id",
                "client_token",
                "action",
                "day_key",
                name="uq_resource_reaction_daily",
            ),
        )

    if not _has_index("resource_reactions", "ix_resource_reactions_id"):
        op.create_index("ix_resource_reactions_id", "resource_reactions", ["id"], unique=False)
    if not _has_index("resource_reactions", "ix_resource_reactions_resource_id"):
        op.create_index("ix_resource_reactions_resource_id", "resource_reactions", ["resource_id"], unique=False)
    if not _has_index("resource_reactions", "ix_resource_reactions_client_token"):
        op.create_index(
            "ix_resource_reactions_client_token",
            "resource_reactions",
            ["client_token"],
            unique=False,
        )
    if not _has_index("resource_reactions", "ix_resource_reactions_action"):
        op.create_index("ix_resource_reactions_action", "resource_reactions", ["action"], unique=False)
    if not _has_index("resource_reactions", "ix_resource_reactions_day_key"):
        op.create_index("ix_resource_reactions_day_key", "resource_reactions", ["day_key"], unique=False)
    if not _has_index("resource_reactions", "ix_resource_reactions_created_at"):
        op.create_index(
            "ix_resource_reactions_created_at",
            "resource_reactions",
            ["created_at"],
            unique=False,
        )


def downgrade() -> None:
    if _has_table("resource_reactions"):
        op.drop_index("ix_resource_reactions_created_at", table_name="resource_reactions")
        op.drop_index("ix_resource_reactions_day_key", table_name="resource_reactions")
        op.drop_index("ix_resource_reactions_action", table_name="resource_reactions")
        op.drop_index("ix_resource_reactions_client_token", table_name="resource_reactions")
        op.drop_index("ix_resource_reactions_resource_id", table_name="resource_reactions")
        op.drop_index("ix_resource_reactions_id", table_name="resource_reactions")
        op.drop_table("resource_reactions")
