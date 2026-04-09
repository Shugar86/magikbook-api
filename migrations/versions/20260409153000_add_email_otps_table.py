"""add email_otps table for email OTP auth

Revision ID: 20260409153000
Revises: 20260323114449
Create Date: 2026-04-09 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260409153000"
down_revision: Union[str, Sequence[str], None] = "20260323114449"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_otps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_email_otps_email"), "email_otps", ["email"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_email_otps_email"), table_name="email_otps")
    op.drop_table("email_otps")
