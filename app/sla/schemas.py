"""
Pydantic Schemas for AICTE CaseConnect SLA Engine.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.enums import Priority, SlaCalendarType, SlaStatus


class SlaPolicyBase(BaseModel):
    name: str = Field(min_length=3, max_length=160)
    category: str = Field(min_length=2, max_length=100)
    priority: Priority | None = None
    bureau_id: int | None = None
    target_duration_days: int = Field(ge=1, le=365)
    calendar_type: SlaCalendarType = SlaCalendarType.CALENDAR_DAYS
    warning_threshold_pct: float = Field(default=75.0, ge=10.0, le=95.0)
    at_risk_threshold_pct: float = Field(default=90.0, ge=20.0, le=99.0)
    escalation_config: dict[str, Any] | None = None
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    is_active: bool = True


class SlaPolicyCreate(SlaPolicyBase):
    pass


class SlaPolicyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=160)
    category: str | None = None
    priority: Priority | None = None
    bureau_id: int | None = None
    target_duration_days: int | None = Field(default=None, ge=1, le=365)
    calendar_type: SlaCalendarType | None = None
    warning_threshold_pct: float | None = Field(default=None, ge=10.0, le=95.0)
    at_risk_threshold_pct: float | None = Field(default=None, ge=20.0, le=99.0)
    escalation_config: dict[str, Any] | None = None
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    is_active: bool | None = None
    change_reason: str | None = None


class SlaPolicyPublic(SlaPolicyBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    version: int
    created_by_id: int | None = None
    updated_by_id: int | None = None
    created_at: datetime
    updated_at: datetime


class SlaPolicyVersionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    policy_id: int
    version: int
    snapshot: dict[str, Any]
    changed_by_id: int | None = None
    change_reason: str | None = None
    created_at: datetime


class SlaPausePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sla_record_id: int
    paused_at: datetime
    paused_by_id: int
    pause_reason: str
    pause_notes: str | None = None
    resumed_at: datetime | None = None
    resumed_by_id: int | None = None
    resume_notes: str | None = None
    duration_seconds: int | None = None


class SlaPauseRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=120)
    notes: str | None = None


class SlaResumeRequest(BaseModel):
    notes: str | None = None


class SlaRecalculateRequest(BaseModel):
    new_policy_id: int | None = None
    reason: str | None = None


class SlaEscalationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    sla_record_id: int
    case_id: int
    escalation_level: int
    trigger_type: str
    previous_authority_id: int | None = None
    new_authority_id: int | None = None
    target_bureau_id: int | None = None
    target_role: str | None = None
    reason: str
    acknowledged: bool
    acknowledged_by_id: int | None = None
    acknowledged_at: datetime | None = None
    created_at: datetime


class SlaEscalationAcknowledgeRequest(BaseModel):
    remarks: str | None = None


class SlaEventPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    sla_record_id: int
    case_id: int
    event_type: str
    actor_id: int | None = None
    previous_state: dict[str, Any] | None = None
    new_state: dict[str, Any] | None = None
    remarks: str | None = None
    created_at: datetime


class CaseSlaRecordPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    case_id: int
    case_ref: str
    policy_id: int
    policy_name: str | None = None
    policy_version: int
    start_time: datetime
    original_deadline: datetime
    current_deadline: datetime
    target_duration_days: int
    calendar_type: str
    status: str
    elapsed_duration_hours: float
    remaining_duration_hours: float
    consumed_percentage: float
    accumulated_paused_seconds: int
    is_paused: bool
    current_pause_id: int | None = None
    completion_time: datetime | None = None
    completed_within_sla: bool | None = None
    actual_duration_hours: float | None = None
    escalation_level: int
    last_evaluated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    pauses: list[SlaPausePublic] = Field(default_factory=list)
    escalations: list[SlaEscalationPublic] = Field(default_factory=list)


class SlaDashboardSummary(BaseModel):
    total_active_records: int
    on_track_count: int
    warning_count: int
    at_risk_count: int
    breached_count: int
    paused_count: int
    completed_count: int
    completed_within_sla_count: int
    # Historical disposal compliance rate: completed within SLA / total completed
    compliance_percentage: float
    # Active in-SLA compliance rate: non-breached active cases / total active
    active_compliance_percentage: float
    # Explicit aliases for clarity and API consumers:
    active_in_sla_percentage: float | None = None
    active_healthy_percentage: float | None = None
    total_escalations_count: int
    generated_at: datetime


class BureauSlaMetric(BaseModel):
    bureau_id: int
    bureau_code: str
    bureau_name: str
    total_cases: int
    pending_cases: int
    on_track: int
    warning: int
    at_risk: int
    breached: int
    paused: int
    completed: int
    compliance_percentage: float
    avg_disposal_days: float
    avg_overdue_days: float
    escalation_count: int


class OfficerSlaMetric(BaseModel):
    officer_id: int
    officer_name: str
    bureau_name: str
    assigned_workload: int
    pending_cases: int
    completed_cases: int
    overdue_cases: int
    compliance_percentage: float
    avg_action_delay_days: float


class SlaRiskAssessment(BaseModel):
    case_id: str
    case_numeric_id: int
    institution_name: str
    category: str
    priority: str
    current_bureau_code: str
    risk_score: int
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    contributing_factors: list[str]
    recommended_action: str
    model_type: str
    evaluated_at: datetime

