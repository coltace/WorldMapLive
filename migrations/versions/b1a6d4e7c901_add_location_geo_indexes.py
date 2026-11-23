"""Add indexes for bounded geographic discovery queries.

Revision ID: b1a6d4e7c901
Revises: 58e09a9e3cb3
Create Date: 2026-11-20
"""
from alembic import op


revision = "b1a6d4e7c901"
down_revision = "58e09a9e3cb3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_map_items_public_geo",
        "map_items",
        ["status", "is_public", "latitude", "longitude"],
        unique=False,
    )
    op.create_index(
        "ix_map_items_status_geo",
        "map_items",
        ["status", "latitude", "longitude"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_map_items_status_geo", table_name="map_items")
    op.drop_index("ix_map_items_public_geo", table_name="map_items")
