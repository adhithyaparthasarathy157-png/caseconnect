"""
AI Intelligence Summary Service.
Generates a daily intelligence briefing from actual database queries.
All outputs are labeled as rule-based — no prediction claims.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.enums import CaseStatus, Priority
from app.models import Alert, Case, Institution


def _get_overdue_cases(db: Session) -> list[dict]:
    now = datetime.now(UTC)
    cases = db.scalars(
        select(Case).where(
            Case.expected_disposal_date.isnot(None),
            Case.status.notin_([CaseStatus.DISPOSED, CaseStatus.CLOSED]),
        )
    ).all()
    overdue = []
    for c in cases:
        disposal = c.expected_disposal_date
        if not disposal.tzinfo:
            disposal = disposal.replace(tzinfo=UTC)
        if disposal < now:
            overdue.append({
                "case_id": c.case_id,
                "institution": c.institution.name if c.institution else "Unknown",
                "category": c.category,
                "overdue_days": (now - disposal).days,
                "status": c.status,
                "priority": c.priority,
            })
    return sorted(overdue, key=lambda x: x["overdue_days"], reverse=True)


def _get_high_activity_institutions(db: Session) -> list[dict]:
    """Institutions with increasing complaint activity (last 30 vs prev 30 days)."""
    now = datetime.now(UTC)
    recent_cutoff = now - timedelta(days=30)
    prev_cutoff = now - timedelta(days=60)

    # Recent 30 days
    recent_stmt = (
        select(Case.institution_id, func.count(Case.id).label("count"))
        .where(Case.receipt_at >= recent_cutoff)
        .group_by(Case.institution_id)
        .subquery()
    )
    prev_stmt = (
        select(Case.institution_id, func.count(Case.id).label("count"))
        .where(Case.receipt_at >= prev_cutoff, Case.receipt_at < recent_cutoff)
        .group_by(Case.institution_id)
        .subquery()
    )
    recent_rows = db.execute(select(recent_stmt)).mappings().all()
    prev_rows = db.execute(select(prev_stmt)).mappings().all()
    prev_map = {r["institution_id"]: r["count"] for r in prev_rows}

    result = []
    for row in recent_rows:
        iid = row["institution_id"]
        recent_count = row["count"]
        prev_count = prev_map.get(iid, 0)
        if recent_count > prev_count and recent_count >= 2:
            institution = db.get(Institution, iid)
            result.append({
                "institution_id": iid,
                "institution_name": institution.name if institution else "Unknown",
                "recent_30_days": recent_count,
                "prev_30_days": prev_count,
                "increase": recent_count - prev_count,
            })
    return sorted(result, key=lambda x: x["increase"], reverse=True)[:10]


def _get_bureau_pendency(db: Session) -> list[dict]:
    """Cases pending per bureau (excluding Disposed/Closed)."""
    rows = db.execute(
        select(Case.current_bureau_id, func.count(Case.id).label("pending"))
        .where(Case.status.notin_([CaseStatus.DISPOSED, CaseStatus.CLOSED]))
        .group_by(Case.current_bureau_id)
    ).mappings().all()

    from app.models import Bureau
    result = []
    for row in rows:
        bureau = db.get(Bureau, row["current_bureau_id"])
        result.append({
            "bureau_id": row["current_bureau_id"],
            "bureau_name": bureau.name if bureau else f"Bureau {row['current_bureau_id']}",
            "pending_cases": row["pending"],
        })
    return sorted(result, key=lambda x: x["pending_cases"], reverse=True)


def _get_status_distribution(db: Session) -> dict[str, int]:
    rows = db.execute(
        select(Case.status, func.count(Case.id).label("count")).group_by(Case.status)
    ).mappings().all()
    return {row["status"]: row["count"] for row in rows}


def _get_priority_distribution(db: Session) -> dict[str, int]:
    rows = db.execute(
        select(Case.priority, func.count(Case.id).label("count")).group_by(Case.priority)
    ).mappings().all()
    return {row["priority"]: row["count"] for row in rows}


def _get_unread_critical_alerts(db: Session) -> int:
    from app.enums import AlertSeverity
    return db.scalar(
        select(func.count(Alert.id)).where(
            Alert.is_read == False,  # noqa: E712
            Alert.severity == AlertSeverity.CRITICAL,
        )
    ) or 0


def generate_intelligence_summary(db: Session) -> dict[str, Any]:
    """Generate daily intelligence briefing from live database data."""
    overdue = _get_overdue_cases(db)
    high_activity = _get_high_activity_institutions(db)
    bureau_pendency = _get_bureau_pendency(db)
    status_dist = _get_status_distribution(db)
    priority_dist = _get_priority_distribution(db)
    critical_alerts = _get_unread_critical_alerts(db)

    total_active = sum(
        v for k, v in status_dist.items()
        if k not in [CaseStatus.DISPOSED, CaseStatus.CLOSED]
    )

    # Generate recommended actions (rule-based)
    recommended_actions = []
    if overdue:
        recommended_actions.append({
            "action": f"Review {len(overdue)} overdue case(s) and update expected disposal dates or escalate",
            "urgency": "High",
            "affected_count": len(overdue),
        })
    if high_activity:
        recommended_actions.append({
            "action": f"Monitor {len(high_activity)} institution(s) showing increased complaint volume",
            "urgency": "Medium",
            "affected_count": len(high_activity),
        })
    if critical_alerts > 0:
        recommended_actions.append({
            "action": f"Acknowledge and resolve {critical_alerts} unread critical alert(s)",
            "urgency": "High",
            "affected_count": critical_alerts,
        })
    escalated_count = status_dist.get(CaseStatus.ESCALATED, 0)
    if escalated_count > 0:
        recommended_actions.append({
            "action": f"Senior officer review required for {escalated_count} escalated case(s)",
            "urgency": "High",
            "affected_count": escalated_count,
        })

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "model_type": "rule_based",
        "disclaimer": "Intelligence summary generated from live database queries. Rule-based analysis only.",
        "summary_metrics": {
            "total_active_cases": total_active,
            "overdue_cases": len(overdue),
            "unread_critical_alerts": critical_alerts,
            "escalated_cases": escalated_count,
            "institutions_with_increased_activity": len(high_activity),
        },
        "status_distribution": status_dist,
        "priority_distribution": priority_dist,
        "overdue_cases": overdue[:10],  # Top 10 overdue
        "high_activity_institutions": high_activity,
        "bureau_pendency": bureau_pendency,
        "recommended_actions": recommended_actions,
    }

