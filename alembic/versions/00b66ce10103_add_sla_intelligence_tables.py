"""add_sla_intelligence_tables

Revision ID: 00b66ce10103
Revises: 00a55bd95e92
Create Date: 2026-10-31 15:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '00b66ce10103'
down_revision = '00a55bd95e92'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. sla_policies
    op.create_table(
        "sla_policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("priority", sa.String(50), nullable=True),
        sa.Column("bureau_id", sa.Integer(), sa.ForeignKey("bureaus.id"), nullable=True),
        sa.Column("target_duration_days", sa.Integer(), nullable=False),
        sa.Column("calendar_type", sa.String(50), nullable=False, server_default="calendar_days"),
        sa.Column("warning_threshold_pct", sa.Float(), nullable=False, server_default="75.0"),
        sa.Column("at_risk_threshold_pct", sa.Float(), nullable=False, server_default="90.0"),
        sa.Column("escalation_config", sa.JSON(), nullable=True),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sla_policies_category", "sla_policies", ["category"])
    op.create_index("ix_sla_policies_category_priority", "sla_policies", ["category", "priority"])
    op.create_index("ix_sla_policies_bureau", "sla_policies", ["bureau_id"])
    op.create_index("ix_sla_policies_active", "sla_policies", ["is_active"])

    # 2. sla_policy_versions
    op.create_table(
        "sla_policy_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("policy_id", sa.Integer(), sa.ForeignKey("sla_policies.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("change_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("policy_id", "version", name="uq_sla_policy_version"),
    )
    op.create_index("ix_sla_policy_versions_policy", "sla_policy_versions", ["policy_id"])

    # 3. case_sla_records
    op.create_table(
        "case_sla_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False, unique=True),
        sa.Column("case_ref", sa.String(40), nullable=False),
        sa.Column("policy_id", sa.Integer(), sa.ForeignKey("sla_policies.id"), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("target_duration_days", sa.Integer(), nullable=False),
        sa.Column("calendar_type", sa.String(50), nullable=False, server_default="calendar_days"),
        sa.Column("status", sa.String(50), nullable=False, server_default="ON_TRACK"),
        sa.Column("elapsed_duration_hours", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("remaining_duration_hours", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("consumed_percentage", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("accumulated_paused_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_paused", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("current_pause_id", sa.Integer(), nullable=True),
        sa.Column("completion_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_within_sla", sa.Boolean(), nullable=True),
        sa.Column("actual_duration_hours", sa.Float(), nullable=True),
        sa.Column("escalation_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_case_sla_records_case_id", "case_sla_records", ["case_id"])
    op.create_index("ix_case_sla_records_case_ref", "case_sla_records", ["case_ref"])
    op.create_index("ix_case_sla_records_policy_id", "case_sla_records", ["policy_id"])
    op.create_index("ix_case_sla_records_status", "case_sla_records", ["status"])
    op.create_index("ix_case_sla_records_deadline", "case_sla_records", ["current_deadline"])

    # 4. sla_pauses
    op.create_table(
        "sla_pauses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sla_record_id", sa.Integer(), sa.ForeignKey("case_sla_records.id"), nullable=False),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paused_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("pause_reason", sa.String(120), nullable=False),
        sa.Column("pause_notes", sa.Text(), nullable=True),
        sa.Column("resumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resumed_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resume_notes", sa.Text(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
    )
    op.create_index("ix_sla_pauses_sla_record_id", "sla_pauses", ["sla_record_id"])

    # 5. sla_escalations
    op.create_table(
        "sla_escalations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("sla_record_id", sa.Integer(), sa.ForeignKey("case_sla_records.id"), nullable=False),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("escalation_level", sa.Integer(), nullable=False),
        sa.Column("trigger_type", sa.String(80), nullable=False),
        sa.Column("previous_authority_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("new_authority_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("target_bureau_id", sa.Integer(), sa.ForeignKey("bureaus.id"), nullable=True),
        sa.Column("target_role", sa.String(80), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("acknowledged_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sla_escalations_sla_record_id", "sla_escalations", ["sla_record_id"])
    op.create_index("ix_sla_escalations_case_id", "sla_escalations", ["case_id"])

    # 6. sla_events
    op.create_table(
        "sla_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("sla_record_id", sa.Integer(), sa.ForeignKey("case_sla_records.id"), nullable=False),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("previous_state", sa.JSON(), nullable=True),
        sa.Column("new_state", sa.JSON(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sla_events_sla_record_id", "sla_events", ["sla_record_id"])
    op.create_index("ix_sla_events_case_id", "sla_events", ["case_id"])
    op.create_index("ix_sla_events_type", "sla_events", ["event_type"])


def downgrade() -> None:
    op.drop_table("sla_events")
    op.drop_table("sla_escalations")
    op.drop_table("sla_pauses")
    op.drop_table("case_sla_records")
    op.drop_table("sla_policy_versions")
    op.drop_table("sla_policies")

