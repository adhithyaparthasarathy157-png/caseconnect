from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import can_view_case, get_current_user, is_broad_viewer
from app.enums import AlertSeverity
from app.intelligence import audit
from app.models import Alert, Case, User
from app.schemas import AlertPublic

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def visible(user: User, alert: Alert) -> bool:
    if is_broad_viewer(user):
        return True
    if alert.case:
        return can_view_case(user, alert.case)
    return alert.bureau_id == user.bureau_id


@router.get("", response_model=list[AlertPublic])
def list_alerts(unread_only: bool = False, alert_type: str | None = None, severity: AlertSeverity | None = None, unresolved_only: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[Alert]:
    query = select(Alert).options(selectinload(Alert.case).selectinload(Case.institution))
    if unread_only:
        query = query.where(Alert.is_read.is_(False))
    if alert_type:
        query = query.where(Alert.alert_type == alert_type)
    if severity:
        query = query.where(Alert.severity == severity)
    if unresolved_only:
        query = query.where(Alert.resolved_at.is_(None))
    return [item for item in db.scalars(query.order_by(Alert.created_at.desc())).all() if visible(user, item)]


def mutate(alert_id: str, operation: str, db: Session, user: User) -> Alert:
    alert = db.scalar(select(Alert).options(selectinload(Alert.case).selectinload(Case.institution)).where(Alert.id == alert_id))
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if not visible(user, alert):
        raise HTTPException(status_code=403, detail="Alert is outside your access scope")
    if operation == "acknowledge" and alert.resolved_at:
        raise HTTPException(status_code=422, detail="A resolved alert cannot be acknowledged")
    if operation == "resolve" and alert.resolved_at:
        raise HTTPException(status_code=422, detail="Alert is already resolved")
    # Read and acknowledgement requests are idempotent.  This prevents a
    # double-click from overwriting timestamps or creating duplicate audit data.
    if operation == "read" and alert.is_read:
        return alert
    if operation == "acknowledge" and alert.acknowledged_at:
        return alert
    if operation == "read":
        alert.is_read = True
    elif operation == "acknowledge":
        alert.is_read, alert.acknowledged_at = True, datetime.now(UTC)
    else:
        alert.is_read, alert.resolved_at, alert.resolved_by_id = True, datetime.now(UTC), user.id
    audit(db, user, "alert", alert.id, f"alert_{operation}")
    db.commit()
    db.refresh(alert)
    return alert


@router.post("/{alert_id}/read", response_model=AlertPublic)
def mark_read(alert_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Alert:
    return mutate(alert_id, "read", db, user)


@router.post("/{alert_id}/acknowledge", response_model=AlertPublic)
def acknowledge(alert_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Alert:
    return mutate(alert_id, "acknowledge", db, user)


@router.post("/{alert_id}/resolve", response_model=AlertPublic)
def resolve(alert_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Alert:
    return mutate(alert_id, "resolve", db, user)
