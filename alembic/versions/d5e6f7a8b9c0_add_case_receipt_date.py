"""add date-only receipt date for cases

Revision ID: d5e6f7a8b9c0
Revises: b4a1c2d3e4f5
"""

import sqlalchemy as sa

from alembic import op

revision = "d5e6f7a8b9c0"
down_revision = "b4a1c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("receipt_date", sa.Date(), nullable=True))
    # Preserve the local calendar date encoded in all historical timestamps.
    # SQLite and PostgreSQL both support this portable DATE projection.
    op.execute("UPDATE cases SET receipt_date = DATE(receipt_at) WHERE receipt_date IS NULL")
    with op.batch_alter_table("cases") as batch:
        batch.alter_column("receipt_date", existing_type=sa.Date(), nullable=False)
    op.create_index("ix_cases_receipt_date_only", "cases", ["receipt_date"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_cases_receipt_date_only", table_name="cases")
    with op.batch_alter_table("cases") as batch:
        batch.drop_column("receipt_date")
