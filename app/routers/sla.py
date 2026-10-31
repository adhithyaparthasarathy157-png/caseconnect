"""
SLA & Pendency Intelligence Router for AICTE CaseConnect.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import can_modify_case, can_view_case, get_current_user, is_broad_viewer, require_roles
from app.enums import Priority, Role, SlaStatus
from app.intelligence import audit
from app.models import Case, CaseSlaRecord, Institution, SlaEscalation, SlaEvent, SlaPause, SlaPolicy, SlaPolicyVersion, User
from app.sla.analytics import export_records_csv, get_bureau_metrics, get_dashboard_summary, get_officer_metrics, get_trends
from app.sla.evaluator import evaluate_all_active, evaluate_sla_record, sync_existing_cases_sla
from app.sla.policy_engine import create_policy, resolve_policy, seed_demo_policies, set_policy_active, update_policy
from app.sla.risk import evaluate_case_pendency_risk, get_risk_dashboard
from app.sla.schemas import (
    BureauSlaMetric,
    CaseSlaRecordPublic,
    OfficerSlaMetric,
    SlaDashboardSummary,
    SlaEscalationAcknowledgeRequest,
    SlaEscalationPublic,
    SlaEventPublic,
    SlaPausePublic,
    SlaPauseRequest,
    SlaPolicyCreate,
    SlaPolicyPublic,
    SlaPolicyUpdate,
    SlaPolicyVersionPublic,
    SlaRecalculateRequest,
    SlaResumeRequest,
    SlaRiskAssessment,
)
from app.sla.tracking import create_sla_record_for_case, pause_sla, recalculate_sla, resume_sla

router = APIRouter(prefix="/api/sla", tags=["sla-intelligence"])


def get_case_by_identifier(db: Session, identifier: str) -> Case:
    """Find case by numeric ID or string reference like CC-2026-00001."""
    clean_id = identifier.strip()
    if clean_id.isdigit():
        c = db.get(Case, int(clean_id))
        if c:
            return c
    c = db.scalar(
        select(Case)
        .options(selectinload(Case.institution), selectinload(Case.current_bureau), selectinload(Case.sla_record))
        .where(Case.case_id == clean_id)
    )
    if not c:
        raise HTTPException(status_code=404, detail=f"Case '{clean_id}' not found")
    return c


# ============================================================================
# SLA Policies Management
# ============================================================================

@router.get("/policies", response_model=list[SlaPolicyPublic])
def list_policies(
    include_inactive: bool = True,
    category: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SlaPolicy]:
    """List all configured SLA policies."""
    query = select(SlaPolicy).order_by(SlaPolicy.category, SlaPolicy.id)
    if not include_inactive:
        query = query.where(SlaPolicy.is_active.is_(True))
    if category:
        query = query.where(func.lower(SlaPolicy.category) == category.strip().lower())
    return list(db.scalars(query).all())


@router.post("/policies", response_model=SlaPolicyPublic, status_code=status.HTTP_201_CREATED)
def new_policy(
    payload: SlaPolicyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.COMPETENT_AUTHORITY)),
) -> SlaPolicy:
    """Create a new SLA policy."""
    return create_policy(db, payload, actor=user)


@router.get("/policies/{policy_id}", response_model=SlaPolicyPublic)
def get_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SlaPolicy:
    """Get single SLA policy by ID."""
    policy = db.get(SlaPolicy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="SLA Policy not found")
    return policy


@router.put("/policies/{policy_id}", response_model=SlaPolicyPublic)
def edit_policy(
    policy_id: int,
    payload: SlaPolicyUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.COMPETENT_AUTHORITY)),
) -> SlaPolicy:
    """Update an SLA policy, creating a new historical version snapshot."""
    policy = db.get(SlaPolicy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="SLA Policy not found")
    return update_policy(db, policy, payload, actor=user)


@router.get("/policies/{policy_id}/versions", response_model=list[SlaPolicyVersionPublic])
def get_policy_versions(
    policy_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SlaPolicyVersion]:
    """Retrieve audit history and immutable snapshots for an SLA policy."""
    policy = db.get(SlaPolicy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="SLA Policy not found")
    return list(
        db.scalars(
            select(SlaPolicyVersion)
            .where(SlaPolicyVersion.policy_id == policy_id)
            .order_by(SlaPolicyVersion.version.desc())
        ).all()
    )


@router.post("/policies/{policy_id}/activate", response_model=SlaPolicyPublic)
def activate_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.COMPETENT_AUTHORITY)),
) -> SlaPolicy:
    policy = db.get(SlaPolicy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="SLA Policy not found")
    return set_policy_active(db, policy, is_active=True, actor=user)


@router.post("/policies/{policy_id}/deactivate", response_model=SlaPolicyPublic)
def deactivate_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.COMPETENT_AUTHORITY)),
) -> SlaPolicy:
    policy = db.get(SlaPolicy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="SLA Policy not found")
    return set_policy_active(db, policy, is_active=False, actor=user)


@router.post("/policies/seed-demo", response_model=list[SlaPolicyPublic])
def seed_policies(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.COMPETENT_AUTHORITY)),
) -> list[SlaPolicy]:
    """Seed baseline illustrative demonstration SLA policies if not present."""
    return seed_demo_policies(db, actor=user)


# ============================================================================
# SLA Tracking & Monitoring Records
# ============================================================================

@router.get("/records")
def list_records(
    case_ref: str | None = None,
    institution_id: int | None = None,
    bureau_id: int | None = None,
    category: str | None = None,
    priority: Priority | None = None,
    sla_status: str | None = Query(default=None, alias="status"),
    is_paused: bool | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Paginated, filtered list of SLA monitoring records."""
    if user.role == Role.INSTITUTION_REPRESENTATIVE:
        raise HTTPException(status_code=403, detail="Institution representatives cannot access administrative SLA monitoring")

    query = select(CaseSlaRecord).join(Case).join(Institution).options(
        selectinload(CaseSlaRecord.case).selectinload(Case.institution),
        selectinload(CaseSlaRecord.case).selectinload(Case.current_bureau),
        selectinload(CaseSlaRecord.case).selectinload(Case.assigned_officer),
        selectinload(CaseSlaRecord.policy),
    )

    if case_ref:
        query = query.where(CaseSlaRecord.case_ref.ilike(f"%{case_ref.strip()}%"))
    if institution_id is not None:
        query = query.where(Case.institution_id == institution_id)
    if bureau_id is not None:
        query = query.where(Case.current_bureau_id == bureau_id)
    if category:
        query = query.where(func.lower(Case.category) == category.strip().lower())
    if priority:
        query = query.where(Case.priority == priority)
    if sla_status:
        query = query.where(CaseSlaRecord.status == sla_status.strip().upper())
    if is_paused is not None:
        query = query.where(CaseSlaRecord.is_paused == is_paused)
    if search:
        s = f"%{search.strip()}%"
        query = query.where(
            (CaseSlaRecord.case_ref.ilike(s)) | (Institution.name.ilike(s)) | (Case.subject.ilike(s))
        )

    all_records = list(db.scalars(query.order_by(CaseSlaRecord.current_deadline.asc())).all())
    visible = [r for r in all_records if r.case and can_view_case(user, r.case)]

    total = len(visible)
    start = (page - 1) * page_size
    items = visible[start : start + page_size]

    results = []
    for r in items:
        case = r.case
        results.append({
            "id": r.id,
            "case_id": r.case_id,
            "case_ref": r.case_ref,
            "institution_name": case.institution.name if case and case.institution else "-",
            "category": case.category if case else "-",
            "priority": case.priority.value if case and hasattr(case.priority, "value") else str(case.priority),
            "current_bureau_code": case.current_bureau.code if case and case.current_bureau else "-",
            "current_bureau_id": case.current_bureau_id if case else None,
            "assigned_officer_name": case.assigned_officer.full_name if case and case.assigned_officer else None,
            "policy_id": r.policy_id,
            "policy_name": r.policy.name if r.policy else "-",
            "policy_version": r.policy_version,
            "start_time": r.start_time.isoformat() if r.start_time else None,
            "original_deadline": r.original_deadline.isoformat() if r.original_deadline else None,
            "current_deadline": r.current_deadline.isoformat() if r.current_deadline else None,
            "target_duration_days": r.target_duration_days,
            "calendar_type": r.calendar_type,
            "status": r.status,
            "elapsed_duration_hours": r.elapsed_duration_hours,
            "remaining_duration_hours": r.remaining_duration_hours,
            "consumed_percentage": r.consumed_percentage,
            "is_paused": r.is_paused,
            "escalation_level": r.escalation_level,
            "completion_time": r.completion_time.isoformat() if r.completion_time else None,
            "completed_within_sla": r.completed_within_sla,
            "last_evaluated_at": r.last_evaluated_at.isoformat() if r.last_evaluated_at else None,
        })

    return {"items": results, "total": total, "page": page, "page_size": page_size}


@router.get("/records/{case_identifier}", response_model=CaseSlaRecordPublic)
def get_case_sla(
    case_identifier: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CaseSlaRecord:
    """Get single SLA tracking record for a complaint case with full pause & escalation history."""
    case = get_case_by_identifier(db, case_identifier)
    if not can_view_case(user, case):
        raise HTTPException(status_code=403, detail="Case is outside your access scope")

    record = db.scalar(
        select(CaseSlaRecord)
        .options(
            selectinload(CaseSlaRecord.pauses),
            selectinload(CaseSlaRecord.escalations),
            selectinload(CaseSlaRecord.policy),
        )
        .where(CaseSlaRecord.case_id == case.id)
    )
    if not record:
        # If no SLA record yet exists, attempt to initialize it deterministically
        record = create_sla_record_for_case(db, case, actor=user)
        if not record:
            raise HTTPException(status_code=404, detail="No applicable SLA policy or record found for this complaint")

    # Attach policy name dynamically for schema
    record.policy_name = record.policy.name if record.policy else None
    return record


@router.get("/records/{case_identifier}/events", response_model=list[SlaEventPublic])
def get_case_sla_events(
    case_identifier: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SlaEvent]:
    """Retrieve complete immutable SLA event history for a case."""
    case = get_case_by_identifier(db, case_identifier)
    if not can_view_case(user, case):
        raise HTTPException(status_code=403, detail="Case is outside your access scope")

    return list(
        db.scalars(
            select(SlaEvent)
            .where(SlaEvent.case_id == case.id)
            .order_by(SlaEvent.created_at.desc())
        ).all()
    )


@router.get("/records/{case_identifier}/pauses", response_model=list[SlaPausePublic])
def get_case_sla_pauses(
    case_identifier: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SlaPause]:
    """Retrieve pause history for an SLA record."""
    case = get_case_by_identifier(db, case_identifier)
    if not can_view_case(user, case):
        raise HTTPException(status_code=403, detail="Case is outside your access scope")
    record = db.scalar(select(CaseSlaRecord).where(CaseSlaRecord.case_id == case.id))
    if not record:
        raise HTTPException(status_code=404, detail="SLA record not found")
    return list(
        db.scalars(
            select(SlaPause)
            .where(SlaPause.sla_record_id == record.id)
            .order_by(SlaPause.paused_at.desc())
        ).all()
    )


# ============================================================================
# SLA Lifecycle Actions: Pause, Resume, Recalculate
# ============================================================================

@router.post("/records/{case_identifier}/pause", response_model=CaseSlaRecordPublic)
def pause_case_sla(
    case_identifier: str,
    payload: SlaPauseRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CaseSlaRecord:
    """Pause SLA tracking with required reason and supporting notes."""
    case = get_case_by_identifier(db, case_identifier)
    if not can_modify_case(user, case):
        raise HTTPException(status_code=403, detail="You do not have permission to pause SLA on this case")

    try:
        record = pause_sla(db, case, reason=payload.reason, notes=payload.notes, actor=user)
        record.policy_name = record.policy.name if record.policy else None
        return record
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/records/{case_identifier}/resume", response_model=CaseSlaRecordPublic)
def resume_case_sla(
    case_identifier: str,
    payload: SlaResumeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CaseSlaRecord:
    """Resume a paused SLA tracking record."""
    case = get_case_by_identifier(db, case_identifier)
    if not can_modify_case(user, case):
        raise HTTPException(status_code=403, detail="You do not have permission to resume SLA on this case")

    try:
        record = resume_sla(db, case, notes=payload.notes, actor=user)
        record.policy_name = record.policy.name if record.policy else None
        return record
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/records/{case_identifier}/recalculate", response_model=CaseSlaRecordPublic)
def recalculate_case_sla(
    case_identifier: str,
    payload: SlaRecalculateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.COMPETENT_AUTHORITY)),
) -> CaseSlaRecord:
    """Administratively recalculate SLA deadline with an updated or explicit policy."""
    case = get_case_by_identifier(db, case_identifier)
    new_policy = db.get(SlaPolicy, payload.new_policy_id) if payload.new_policy_id else None
    if payload.new_policy_id and not new_policy:
        raise HTTPException(status_code=404, detail="Specified target policy does not exist")

    try:
        record = recalculate_sla(db, case, new_policy=new_policy, reason=payload.reason, actor=user)
        record.policy_name = record.policy.name if record.policy else None
        return record
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


# ============================================================================
# Automated Evaluation & Sync
# ============================================================================

@router.post("/evaluate")
def run_evaluation(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, int]:
    """Run automated SLA evaluation across all active complaints."""
    if user.role == Role.INSTITUTION_REPRESENTATIVE:
        raise HTTPException(status_code=403, detail="Unauthorized")
    return evaluate_all_active(db)


@router.post("/sync-cases")
def sync_cases(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.COMPETENT_AUTHORITY)),
) -> dict[str, int]:
    """Backfill/initialize SLA records for existing database complaints without modifying cases."""
    return sync_existing_cases_sla(db, actor=user)


# ============================================================================
# Escalations Centre
# ============================================================================

@router.get("/escalations", response_model=list[SlaEscalationPublic])
def list_escalations(
    acknowledged: bool | None = None,
    bureau_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SlaEscalation]:
    """List SLA escalations across complaints."""
    if user.role == Role.INSTITUTION_REPRESENTATIVE:
        raise HTTPException(status_code=403, detail="Unauthorized")

    query = select(SlaEscalation).join(Case).options(selectinload(SlaEscalation.case))
    if acknowledged is not None:
        query = query.where(SlaEscalation.acknowledged == acknowledged)
    if bureau_id:
        query = query.where(SlaEscalation.target_bureau_id == bureau_id)

    candidates = list(db.scalars(query.order_by(SlaEscalation.created_at.desc())).all())
    return [e for e in candidates if e.case and can_view_case(user, e.case)]


@router.post("/escalations/{escalation_id}/acknowledge", response_model=SlaEscalationPublic)
def acknowledge_escalation(
    escalation_id: str,
    payload: SlaEscalationAcknowledgeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SlaEscalation:
    """Acknowledge an automated SLA escalation."""
    esc = db.get(SlaEscalation, escalation_id)
    if not esc:
        raise HTTPException(status_code=404, detail="Escalation record not found")
    if not can_view_case(user, esc.case):
        raise HTTPException(status_code=403, detail="Case is outside your access scope")

    if esc.acknowledged:
        return esc

    ack_time = datetime.now(UTC)
    esc.acknowledged = True
    esc.acknowledged_by_id = user.id
    esc.acknowledged_at = ack_time

    audit(
        db,
        user,
        "sla_escalation",
        esc.id,
        "escalation_acknowledged",
        {"remarks": payload.remarks},
    )
    db.commit()
    db.refresh(esc)
    return esc


# ============================================================================
# Analytics & Reports
# ============================================================================

@router.get("/dashboard", response_model=SlaDashboardSummary)
def get_dashboard(
    bureau_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SlaDashboardSummary:
    """SLA Overview KPI cards and status distribution."""
    if user.role == Role.INSTITUTION_REPRESENTATIVE:
        raise HTTPException(status_code=403, detail="Unauthorized")

    effective_bureau = bureau_id
    if not is_broad_viewer(user) and user.bureau_id:
        effective_bureau = user.bureau_id

    return get_dashboard_summary(db, bureau_id=effective_bureau)


@router.get("/analytics/bureaus", response_model=list[BureauSlaMetric])
def get_bureaus_analytics(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[BureauSlaMetric]:
    """Bureau-wise SLA performance analytics."""
    if user.role == Role.INSTITUTION_REPRESENTATIVE:
        raise HTTPException(status_code=403, detail="Unauthorized")
    return get_bureau_metrics(db)


@router.get("/analytics/officers", response_model=list[OfficerSlaMetric])
def get_officers_analytics(
    bureau_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[OfficerSlaMetric]:
    """Officer-level workload and compliance analytics. Permission-controlled."""
    if user.role not in {Role.ADMIN, Role.SENIOR_MANAGEMENT, Role.COMPETENT_AUTHORITY, Role.RB_OFFICER, Role.PGRC_OFFICER}:
        raise HTTPException(status_code=403, detail="Officer analytics requires administrative permission")

    effective_bureau = bureau_id
    if not is_broad_viewer(user) and user.bureau_id:
        effective_bureau = user.bureau_id

    return get_officer_metrics(db, bureau_id=effective_bureau)


@router.get("/analytics/trends")
def get_analytics_trends(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Monthly compliance trend, category disposal time, and distribution."""
    if user.role == Role.INSTITUTION_REPRESENTATIVE:
        raise HTTPException(status_code=403, detail="Unauthorized")
    return get_trends(db)


@router.get("/reports/export-csv")
def export_csv(
    bureau_id: int | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Export SLA monitoring table data as a downloadable CSV."""
    if user.role == Role.INSTITUTION_REPRESENTATIVE:
        raise HTTPException(status_code=403, detail="Unauthorized")

    query = select(CaseSlaRecord).join(Case).options(
        selectinload(CaseSlaRecord.case).selectinload(Case.institution),
        selectinload(CaseSlaRecord.case).selectinload(Case.current_bureau),
        selectinload(CaseSlaRecord.case).selectinload(Case.assigned_officer),
        selectinload(CaseSlaRecord.policy),
    )
    if bureau_id:
        query = query.where(Case.current_bureau_id == bureau_id)
    if status_filter:
        query = query.where(CaseSlaRecord.status == status_filter.strip().upper())

    records = list(db.scalars(query.order_by(CaseSlaRecord.current_deadline)).all())
    visible = [r for r in records if r.case and can_view_case(user, r.case)]
    return export_records_csv(visible)


# ============================================================================
# AI Pendency Risk Intelligence
# ============================================================================

@router.get("/risk/dashboard")
def get_ai_risk_dashboard(
    bureau_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """AI pendency risk intelligence summary for AI Command Centre."""
    if user.role == Role.INSTITUTION_REPRESENTATIVE:
        raise HTTPException(status_code=403, detail="Unauthorized")

    effective_bureau = bureau_id
    if not is_broad_viewer(user) and user.bureau_id:
        effective_bureau = user.bureau_id

    return get_risk_dashboard(db, bureau_id=effective_bureau)


@router.get("/risk/{case_identifier}", response_model=SlaRiskAssessment)
def get_case_risk(
    case_identifier: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SlaRiskAssessment:
    """Detailed explainable pendency risk assessment for a single complaint."""
    case = get_case_by_identifier(db, case_identifier)
    if not can_view_case(user, case):
        raise HTTPException(status_code=403, detail="Case is outside your access scope")

    return evaluate_case_pendency_risk(db, case)

