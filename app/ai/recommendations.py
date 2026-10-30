"""
Rule-based case recommendation service.
Produces bureau, priority, next-action recommendations with explicit evidence.
All recommendations require human approval before consequential actions.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import CaseStatus, Priority
from app.models import Case, OverlapCandidate, User

# ------------------------------------------------------------------
# Bureau/Cell routing rules  (rule-based — not a trained model)
# ------------------------------------------------------------------
_CATEGORY_BUREAU: dict[str, str] = {
    "Academic": "PGRC",
    "Financial": "Finance Cell",
    "Infrastructure": "Regional Bureau",
    "Faculty": "PGRC",
    "Accreditation": "Accreditation Bureau",
    "Affiliation": "Regional Bureau",
    "Admission": "PGRC",
    "Conduct": "PGRC",
    "Examination": "PGRC",
    "Other": "PGRC",
}

_STATUS_NEXT_ACTION: dict[CaseStatus, str] = {
    CaseStatus.RECEIVED: "Assign case to relevant bureau officer for initial review",
    CaseStatus.UNDER_REVIEW: "Complete document scrutiny and raise deficiency notice if documents are incomplete",
    CaseStatus.UNDER_PROCESS: "Progress investigation, coordinate with institution if needed",
    CaseStatus.PENDING_INSTITUTION_RESPONSE: "Await institution response; escalate if overdue beyond 15 working days",
    CaseStatus.TRANSFERRED: "Confirm receiving bureau has acknowledged the case",
    CaseStatus.ESCALATED: "Senior officer to review and make final determination",
    CaseStatus.DISPOSED: "Confirm all closure conditions satisfied; notify institution",
    CaseStatus.CLOSED: "Archive case and update analytics",
}


def _bureau_recommendation(case: Case) -> dict[str, Any]:
    """Map category → recommended bureau. Rule-based."""
    category = (case.category or "").strip()
    bureau = _CATEGORY_BUREAU.get(category, "PGRC")
    confidence = 0.85 if category in _CATEGORY_BUREAU else 0.50
    return {
        "recommended_bureau": bureau,
        "confidence": confidence,
        "rule_name": "category_bureau_mapping",
        "evidence": [f"Case category '{category}' maps to {bureau} per routing rules"],
        "model_type": "rule_based",
    }


def _priority_recommendation(case: Case, db: Session) -> dict[str, Any]:
    """Compute priority score with explicit factors. Rule-based risk assessment."""
    factors: list[str] = []
    score = 0

    # Pending duration
    now = datetime.now(UTC)
    receipt = case.receipt_at if case.receipt_at.tzinfo else case.receipt_at.replace(tzinfo=UTC)
    pending_days = (now - receipt).days
    if pending_days > 90:
        score += 40
        factors.append(f"Case pending for {pending_days} days (>90 days threshold)")
    elif pending_days > 60:
        score += 25
        factors.append(f"Case pending for {pending_days} days (>60 days threshold)")
    elif pending_days > 30:
        score += 10
        factors.append(f"Case pending for {pending_days} days (>30 days threshold)")

    # Overdue check
    if case.expected_disposal_date:
        disposal = case.expected_disposal_date
        if not disposal.tzinfo:
            disposal = disposal.replace(tzinfo=UTC)
        if disposal < now:
            overdue_days = (now - disposal).days
            score += 30
            factors.append(f"Case overdue by {overdue_days} days past expected disposal date")

    # Status-based urgency
    if case.status == CaseStatus.ESCALATED:
        score += 20
        factors.append("Case is currently escalated")
    elif case.status == CaseStatus.PENDING_INSTITUTION_RESPONSE:
        score += 5
        factors.append("Awaiting institution response")

    # Category-based inherent risk (configurable, not official AICTE SLAs)
    high_risk_categories = {"Financial", "Accreditation", "Conduct"}
    if case.category in high_risk_categories:
        score += 15
        factors.append(f"Category '{case.category}' carries higher inherent risk")

    # Existing priority boost
    if case.priority == Priority.HIGH:
        score += 10
        factors.append("Currently assigned HIGH priority")
    elif case.priority == Priority.CRITICAL:
        score += 20
        factors.append("Currently assigned CRITICAL priority")

    # Institution case history
    institution_case_count = db.scalar(
        select(Case).where(Case.institution_id == case.institution_id).with_only_columns(
            *[Case.id]
        )
    )
    total_cases = db.execute(
        select(Case.id).where(Case.institution_id == case.institution_id)
    ).scalars().all()
    if len(total_cases) > 5:
        score += 10
        factors.append(f"Institution has {len(total_cases)} total cases on record")

    score = min(score, 100)

    if score >= 70:
        priority_level = "Critical"
    elif score >= 45:
        priority_level = "High"
    elif score >= 20:
        priority_level = "Medium"
    else:
        priority_level = "Low"

    return {
        "priority_level": priority_level,
        "priority_score": score,
        "factors": factors,
        "pending_days": pending_days,
        "rule_name": "composite_priority_scoring",
        "model_type": "rule_based_risk_assessment",
        "explanation": f"Score {score}/100 based on {len(factors)} rule-based factors. Requires human review before any consequential action.",
    }


def _next_action_recommendation(case: Case) -> dict[str, Any]:
    """Suggest next action based on current status. Template-based."""
    action = _STATUS_NEXT_ACTION.get(case.status, "Review current status and determine appropriate next step")
    return {
        "recommended_next_action": action,
        "rule_name": "status_next_action_mapping",
        "model_type": "rule_based",
        "evidence": [f"Current status '{case.status}' → standard next action"],
    }


def _coordination_check(case: Case, db: Session) -> dict[str, Any]:
    """Check if cross-bureau coordination is needed."""
    overlaps = db.scalars(
        select(OverlapCandidate).where(
            ((OverlapCandidate.case_low_id == case.id) | (OverlapCandidate.case_high_id == case.id))
        )
    ).all()
    cross_bureau = [o for o in overlaps if o.is_cross_bureau]
    needs_coordination = len(cross_bureau) > 0
    return {
        "needs_cross_bureau_coordination": needs_coordination,
        "overlap_count": len(overlaps),
        "cross_bureau_overlap_count": len(cross_bureau),
        "rule_name": "overlap_coordination_check",
        "model_type": "rule_based",
        "evidence": [f"Found {len(cross_bureau)} cross-bureau overlap(s) for this case"] if needs_coordination else ["No cross-bureau overlaps detected"],
    }


def get_case_recommendation(case: Case, db: Session, actor: User | None = None) -> dict[str, Any]:
    """Return comprehensive recommendation for a case. All outputs are rule-based."""
    bureau = _bureau_recommendation(case)
    priority = _priority_recommendation(case, db)
    next_action = _next_action_recommendation(case)
    coordination = _coordination_check(case, db)

    return {
        "case_id": case.case_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "recommendation_version": "1.0",
        "model_type": "rule_based",
        "disclaimer": "All recommendations are rule-based and require human review before consequential action.",
        "bureau_recommendation": bureau,
        "priority_assessment": priority,
        "next_action": next_action,
        "coordination_check": coordination,
        "summary": (
            f"Priority: {priority['priority_level']} (score {priority['priority_score']}/100). "
            f"Recommended bureau: {bureau['recommended_bureau']}. "
            f"Next action: {next_action['recommended_next_action']}"
        ),
    }

