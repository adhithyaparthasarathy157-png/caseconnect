"""add_complaint_submissions_table

Revision ID: 00a55bd95e92
Revises: 00325e22102f
Create Date: 2026-10-30 22:21:38.584545
"""
from alembic import op
import sqlalchemy as sa

revision = '00a55bd95e92'
down_revision = '00325e22102f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "complaint_submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("submission_ref", sa.String(20), nullable=False, unique=True),
        sa.Column("institution_id", sa.Integer(), sa.ForeignKey("institutions.id"), nullable=True),
        sa.Column("permanent_id_submitted", sa.String(64), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("subject", sa.String(300), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("incident_date", sa.String(30), nullable=True),
        sa.Column("contact_info", sa.String(255), nullable=True),
        sa.Column("previous_complaint_ref", sa.String(80), nullable=True),
        sa.Column("screening_status", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("screening_outcome", sa.String(50), nullable=True),
        sa.Column("screening_outcome_json", sa.JSON(), nullable=True),
        sa.Column("admin_override", sa.String(50), nullable=True),
        sa.Column("admin_override_reason", sa.Text(), nullable=True),
        sa.Column("admin_override_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("admin_override_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("parent_submission_id", sa.Integer(), sa.ForeignKey("complaint_submissions.id"), nullable=True),
        sa.Column("submitted_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("is_synthetic_demo", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("demo_scenario_id", sa.String(30), nullable=True),
        sa.Column("expected_demo_outcome", sa.String(50), nullable=True),
        sa.Column("registered_case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_submissions_institution_id", "complaint_submissions", ["institution_id"])
    op.create_index("ix_submissions_status", "complaint_submissions", ["screening_status"])
    op.create_index("ix_submissions_permanent_id", "complaint_submissions", ["permanent_id_submitted"])
    op.create_index("ix_submissions_ref", "complaint_submissions", ["submission_ref"])


def downgrade() -> None:
    op.drop_index("ix_submissions_ref", "complaint_submissions")
    op.drop_index("ix_submissions_permanent_id", "complaint_submissions")
    op.drop_index("ix_submissions_status", "complaint_submissions")
    op.drop_index("ix_submissions_institution_id", "complaint_submissions")
    op.drop_table("complaint_submissions")
