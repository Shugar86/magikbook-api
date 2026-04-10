"""add vk video embed ids for iframe player

Revision ID: 20260410120000
Revises: 20260409153000
Create Date: 2026-04-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260410120000"
down_revision: Union[str, Sequence[str], None] = "20260409153000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("prompts", sa.Column("vk_video_owner_id", sa.Integer(), nullable=True))
    op.add_column("prompts", sa.Column("vk_video_id", sa.Integer(), nullable=True))
    op.add_column("prompts", sa.Column("vk_video_hash", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("prompts", "vk_video_hash")
    op.drop_column("prompts", "vk_video_id")
    op.drop_column("prompts", "vk_video_owner_id")
