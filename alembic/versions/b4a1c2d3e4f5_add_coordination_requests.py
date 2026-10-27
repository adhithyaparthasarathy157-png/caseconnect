"""add persisted cross-bureau coordination requests

Revision ID: b4a1c2d3e4f5
Revises: f3cf3fa5cbb8
"""
import sqlalchemy as sa

from alembic import op

revision = "b4a1c2d3e4f5"
down_revision = "f3cf3fa5cbb8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "coordination_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("overlap_id", sa.Integer(), nullable=False),
        sa.Column("requesting_case_id", sa.Integer(), nullable=False),
        sa.Column("receiving_case_id", sa.Integer(), nullable=False),
        sa.Column("requesting_bureau_id", sa.Integer(), nullable=False),
        sa.Column("receiving_bureau_id", sa.Integer(), nullable=False),
        sa.Column("requester_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "RESPONDED", "MORE_INFORMATION", "RESOLVED", name="coordinationstatus"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column("responded_by_id", sa.Integer(), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["overlap_id"], ["overlap_candidates.id"]),
        sa.ForeignKeyConstraint(["receiving_bureau_id"], ["bureaus.id"]),
        sa.ForeignKeyConstraint(["receiving_case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["requesting_bureau_id"], ["bureaus.id"]),
        sa.ForeignKeyConstraint(["requesting_case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["responded_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("overlap_id", name="uq_coordination_overlap"),
    )
    op.create_index(op.f("ix_coordination_requests_overlap_id"), "coordination_requests", ["overlap_id"], unique=False)
    op.create_index(op.f("ix_coordination_requests_requesting_case_id"), "coordination_requests", ["requesting_case_id"], unique=False)
    op.create_index(op.f("ix_coordination_requests_receiving_case_id"), "coordination_requests", ["receiving_case_id"], unique=False)
    op.create_index(op.f("ix_coordination_requests_requesting_bureau_id"), "coordination_requests", ["requesting_bureau_id"], unique=False)
    op.create_index(op.f("ix_coordination_requests_receiving_bureau_id"), "coordination_requests", ["receiving_bureau_id"], unique=False)
    op.create_index(op.f("ix_coordination_requests_requester_id"), "coordination_requests", ["requester_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_coordination_requests_requester_id"), table_name="coordination_requests")
    op.drop_index(op.f("ix_coordination_requests_receiving_bureau_id"), table_name="coordination_requests")
    op.drop_index(op.f("ix_coordination_requests_requesting_bureau_id"), table_name="coordination_requests")
    op.drop_index(op.f("ix_coordination_requests_receiving_case_id"), table_name="coordination_requests")
    op.drop_index(op.f("ix_coordination_requests_requesting_case_id"), table_name="coordination_requests")
    op.drop_index(op.f("ix_coordination_requests_overlap_id"), table_name="coordination_requests")
    op.drop_table("coordination_requests")
