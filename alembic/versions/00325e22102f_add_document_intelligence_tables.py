"""add_document_intelligence_tables

Revision ID: 00325e22102f
Revises: e1f2a3b4c5d6
Create Date: 2026-10-30 21:48:28.905792
"""
from alembic import op
import sqlalchemy as sa

revision = '00325e22102f'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_analyses",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("case_numeric_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("case_id", sa.String(length=40), nullable=False),
        sa.Column("institution_id", sa.Integer(), sa.ForeignKey("institutions.id"), nullable=False),
        sa.Column("document_type", sa.String(length=100), nullable=False),
        sa.Column("input_source", sa.String(length=50), nullable=False, server_default="manual_ocr"),
        sa.Column("fixture_id", sa.String(length=100), nullable=True),
        sa.Column("ocr_text", sa.Text(), nullable=False),
        sa.Column("ocr_text_snippet", sa.String(length=500), nullable=False),
        sa.Column("extracted_fields", sa.JSON(), nullable=False),
        sa.Column("field_evidence", sa.JSON(), nullable=False),
        sa.Column("findings", sa.JSON(), nullable=False),
        sa.Column("classification_confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("top_alternatives", sa.JSON(), nullable=False),
        sa.Column("classification_method", sa.String(length=100), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("analysis_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("parent_analysis_id", sa.Integer(), sa.ForeignKey("document_analyses.id"), nullable=True),
        sa.Column("pre_scrutiny_status", sa.String(length=50), nullable=False),
        sa.Column("recommended_action", sa.String(length=500), nullable=False),
        sa.Column("requires_human_review", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("generated_deficiency_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_doc_analyses_case_id", "document_analyses", ["case_numeric_id"])
    op.create_index("ix_doc_analyses_institution_id", "document_analyses", ["institution_id"])
    op.create_index("ix_doc_analyses_status", "document_analyses", ["pre_scrutiny_status"])

    op.create_table(
        "document_analysis_reviews",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("analysis_id", sa.Integer(), sa.ForeignKey("document_analyses.id"), nullable=False),
        sa.Column("reviewer_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("review_action", sa.String(length=50), nullable=False),
        sa.Column("reviewer_comments", sa.Text(), nullable=True),
        sa.Column("finding_updates", sa.JSON(), nullable=False),
        sa.Column("final_review_status", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_document_analysis_reviews_analysis_id", "document_analysis_reviews", ["analysis_id"])


def downgrade() -> None:
    op.drop_index("ix_document_analysis_reviews_analysis_id", table_name="document_analysis_reviews")
    op.drop_table("document_analysis_reviews")
    op.drop_index("ix_doc_analyses_status", table_name="document_analyses")
    op.drop_index("ix_doc_analyses_institution_id", table_name="document_analyses")
    op.drop_index("ix_doc_analyses_case_id", table_name="document_analyses")
    op.drop_table("document_analyses")
