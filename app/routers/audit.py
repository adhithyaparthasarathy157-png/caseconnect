from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.enums import Role
from app.models import AuditEvent, User
from app.schemas import AuditEventPublic

router = APIRouter(prefix="/api/audit-events", tags=["audit"])


@router.get("", response_model=list[AuditEventPublic])
def list_audit_events(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[AuditEvent]:
    if user.role not in {Role.ADMIN, Role.COMPETENT_AUTHORITY, Role.SENIOR_MANAGEMENT}:
        raise HTTPException(status_code=403, detail="Audit history is restricted")
    return list(db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc())).all())
