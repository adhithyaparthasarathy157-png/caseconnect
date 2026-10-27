"""Explicit repeatable prototype deadline monitor; no continuous scheduler is implied."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.enums import AlertSeverity, CaseStatus
from app.intelligence import create_alert, refresh_overlaps
from app.models import Case


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def run_monitor(db: Session, warning_days: int = 7) -> dict[str, int]:
    today = datetime.now(UTC)
    upcoming = today + timedelta(days=warning_days)
    cases = db.scalars(select(Case).options(selectinload(Case.institution)).where(Case.expected_disposal_date.is_not(None), Case.status.notin_([CaseStatus.CLOSED, CaseStatus.DISPOSED]))).all()
    created = 0
    for case in cases:
        deadline = case.expected_disposal_date
        if as_utc(deadline) < today:
            create_alert(db, key=f"deadline:overdue:{case.id}", alert_type="overdue", severity=AlertSeverity.CRITICAL,
                         title="Case overdue", message="Expected disposal date has passed.", case=case)
            created += 1
        elif as_utc(deadline) <= upcoming:
            create_alert(db, key=f"deadline:upcoming:{case.id}", alert_type="upcoming_deadline", severity=AlertSeverity.WARNING,
                         title="Deadline approaching", message=f"Expected disposal is within {warning_days} prototype warning days.", case=case)
            created += 1
        if case.next_action and not case.assigned_officer_id:
            create_alert(db, key=f"pending-action:{case.id}", alert_type="pending_action", severity=AlertSeverity.INFO,
                         title="Pending action needs assignment", message="A next action exists but no officer is assigned.", case=case)
    overlaps = refresh_overlaps(db)
    db.commit()
    return {"deadline_candidates": len(cases), "alerts_considered": created, "overlaps_refreshed": overlaps}
