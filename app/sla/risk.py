"""
AI Pendency Risk Intelligence Service for AICTE CaseConnect.

Estimates the risk that an active complaint may miss its SLA deadline based on:
- SLA consumption percentage
- Time elapsed since last recorded action
- Bureau pending workload friction
- Case priority and historical category complexity
- Previous bureau transfers and escalations

Explicitly labeled as a deterministic rule-based heuristic with full explainability.
Does not alter official deadlines or automate complaint disposal.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.enums import ActionType, CaseStatus, Priority
from app.models import Case, CaseEvent, CaseSlaRecord, SlaEscalation
from app.sla.calendar import ensure_utc
from app.sla.schemas import SlaRiskAssessment


def evaluate_case_pendency_risk(db: Session, case: Case) -> SlaRiskAssessment:
    """
    Compute explainable pendency risk assessment for a complaint case.
    Returns structured risk score (0-100), risk level, and contributing factors.
    """
    now_dt = datetime.now(UTC)
    factors: list[str] = []
    base_score = 15  # baseline nominal risk

    rec = case.sla_record
    if not rec:
        from app.sla.tracking import create_sla_record_for_case
        rec = create_sla_record_for_case(db, case)

    # 1. Consumed SLA percentage factor
    consumed = rec.consumed_percentage if rec else 0.0
    if consumed >= 100.0:
        base_score += 45
        factors.append(f"Target SLA deadline has elapsed ({round(consumed)}% consumed)")
    elif consumed >= 90.0:
        base_score += 35
        factors.append(f"Approaching immediate SLA breach ({round(consumed)}% consumed)")
    elif consumed >= 75.0:
        base_score += 25
        factors.append(f"In warning window ({round(consumed)}% consumed)")
    elif consumed >= 50.0:
        base_score += 15
        factors.append(f"Over half of nominal duration consumed ({round(consumed)}%)")
    else:
        factors.append(f"Early in lifecycle ({round(consumed)}% consumed)")

    # 2. Priority factor
    if case.priority == Priority.CRITICAL:
        base_score += 20
        factors.append("Critical priority requires expedited handling")
    elif case.priority == Priority.HIGH:
        base_score += 10
        factors.append("High priority complaint")
    elif case.priority == Priority.LOW:
        base_score -= 5

    # 3. Time since last recorded action (inactivity friction)
    if case.last_action_at:
        days_inactive = max(0.0, (now_dt - ensure_utc(case.last_action_at)).total_seconds() / 86400.0)
        if days_inactive >= 14.0:
            base_score += 20
            factors.append(f"Prolonged inactivity: No action recorded for {round(days_inactive)} days")
        elif days_inactive >= 7.0:
            base_score += 10
            factors.append(f"Case inactive for {round(days_inactive)} days without workflow progress")

    # 4. Bureau workload friction
    bureau_pending_count = db.scalar(
        select(func.count(Case.id)).where(
            Case.current_bureau_id == case.current_bureau_id,
            Case.status.notin_([CaseStatus.DISPOSED, CaseStatus.CLOSED]),
        )
    ) or 0
    if bureau_pending_count >= 15:
        base_score += 15
        factors.append(f"High bureau workload: {bureau_pending_count} active complaints in current bureau")
    elif bureau_pending_count >= 8:
        base_score += 8
        factors.append(f"Moderate bureau pending queue: {bureau_pending_count} cases")

    # 5. Inter-bureau transfers & previous escalations
    transfer_count = db.scalar(
        select(func.count(CaseEvent.id)).where(
            CaseEvent.case_id == case.id,
            CaseEvent.action_type == ActionType.TRANSFERRED,
        )
    ) or 0
    if transfer_count > 0:
        base_score += 10 * transfer_count
        factors.append(f"Transferred between bureaus {transfer_count} time(s)")

    esc_count = db.scalar(
        select(func.count(SlaEscalation.id)).where(
            SlaEscalation.case_id == case.id,
        )
    ) or 0
    if esc_count > 0:
        base_score += 12 * esc_count
        factors.append(f"Subject to {esc_count} previous escalation alert(s)")

    # 6. Unassigned officer risk
    if not case.assigned_officer_id:
        base_score += 12
        factors.append("No designated officer assigned to case")

    # 7. Paused status context
    if rec and rec.is_paused:
        base_score = max(base_score - 10, 20)
        factors.append("SLA is currently paused; evaluation frozen pending external event")

    # Final score clamped 0 - 100
    final_score = max(5, min(98, base_score))

    # Risk level classification
    if final_score >= 80:
        risk_level = "CRITICAL"
        action = "Immediate administrative intervention required: Reassign officer or request priority review"
    elif final_score >= 65:
        risk_level = "HIGH"
        action = "High pendency risk: Schedule for bureau review within 48 hours"
    elif final_score >= 40:
        risk_level = "MEDIUM"
        action = "Moderate risk: Monitor workflow progress and check for pending institution replies"
    else:
        risk_level = "LOW"
        action = "Normal progression: Case on track within acceptable parameters"

    inst_name = case.institution.name if case.institution else "Unknown"
    prio_str = case.priority.value if hasattr(case.priority, "value") else str(case.priority)
    bureau_code = case.current_bureau.code if case.current_bureau else "-"

    return SlaRiskAssessment(
        case_id=case.case_id,
        case_numeric_id=case.id,
        institution_name=inst_name,
        category=case.category,
        priority=prio_str,
        current_bureau_code=bureau_code,
        risk_score=final_score,
        risk_level=risk_level,
        contributing_factors=factors,
        recommended_action=action,
        model_type="deterministic_rule_heuristic",
        evaluated_at=now_dt,
    )


def get_risk_dashboard(db: Session, bureau_id: int | None = None) -> dict[str, Any]:
    """Summary of high pendency risk cases for the AI Command Centre."""
    query = select(Case).options(
        selectinload(Case.institution),
        selectinload(Case.current_bureau),
        selectinload(Case.sla_record),
    ).where(Case.status.notin_([CaseStatus.DISPOSED, CaseStatus.CLOSED]))

    if bureau_id:
        query = query.where(Case.current_bureau_id == bureau_id)

    active_cases = list(db.scalars(query).all())
    assessments = [evaluate_case_pendency_risk(db, c) for c in active_cases]

    critical_cases = [a for a in assessments if a.risk_level == "CRITICAL"]
    high_cases = [a for a in assessments if a.risk_level == "HIGH"]
    medium_cases = [a for a in assessments if a.risk_level == "MEDIUM"]
    low_cases = [a for a in assessments if a.risk_level == "LOW"]

    # Top 10 cases requiring immediate administrative attention
    top_at_risk = sorted(assessments, key=lambda x: x.risk_score, reverse=True)[:10]

    return {
        "total_evaluated": len(assessments),
        "critical_count": len(critical_cases),
        "high_risk_count": len(high_cases),
        "medium_risk_count": len(medium_cases),
        "low_risk_count": len(low_cases),
        "top_at_risk_cases": [a.model_dump() for a in top_at_risk],
        "generated_at": datetime.now(UTC).isoformat(),
        "disclaimer": "Rule-based pendency risk heuristic based on case features and workload metrics. Requires human authorization.",
    }

