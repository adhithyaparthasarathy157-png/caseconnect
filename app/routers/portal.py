"""Institution-representative portal endpoints with server-side institution isolation."""
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import can_view_case, get_current_user
from app.enums import ActionType, CaseStatus, Role
from app.models import Alert, Case, CaseEvent, Institution, User
from app.schemas import AlertPublic, CaseEventPublic, CasePublic, InstitutionPublic
from app.services import append_event, audit, now

router = APIRouter(prefix="/api/portal", tags=["institution portal"])


class PortalResponseCreate(BaseModel):
    remarks: str = Field(min_length=2, max_length=2000, description="Clarification, response, or explanation")


def representative(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.INSTITUTION_REPRESENTATIVE or user.institution_id is None:
        raise HTTPException(status_code=403, detail="Institution representative access is required")
    return user


@router.get("/overview")
def overview(db: Session = Depends(get_db), user: User = Depends(representative)) -> dict:
    cases = list(db.scalars(select(Case).where(Case.institution_id == user.institution_id).order_by(Case.updated_at.desc())).all())
    alerts = [item for item in db.scalars(select(Alert).where(Alert.case_id.in_([case.id for case in cases] or [-1]))).all() if can_view_case(user, item.case)]
    statuses = Counter(case.status.value for case in cases)
    case_ids = [c.id for c in cases]
    recent_events = []
    if case_ids:
        recent_events = list(db.scalars(
            select(CaseEvent)
            .where(CaseEvent.case_id.in_(case_ids))
            .order_by(CaseEvent.created_at.desc())
            .limit(8)
        ).all())
    return {
        "institution_id": user.institution_id,
        "total_applications": len(cases),
        "under_review": statuses[CaseStatus.UNDER_REVIEW.value] + statuses[CaseStatus.UNDER_PROCESS.value],
        "action_required": statuses[CaseStatus.PENDING_INSTITUTION_RESPONSE.value] + len([item for item in alerts if not item.resolved_at]),
        "approved": statuses[CaseStatus.DISPOSED.value],
        "rejected": statuses[CaseStatus.CLOSED.value],
        "recent_applications": [CasePublic.model_validate(case) for case in cases[:8]],
        "recent_activity": [CaseEventPublic.model_validate(item) for item in recent_events],
    }


@router.get("/applications", response_model=list[CasePublic])
def applications(case_id: str | None = None, status: CaseStatus | None = None, db: Session = Depends(get_db), user: User = Depends(representative)) -> list[Case]:
    query = select(Case).where(Case.institution_id == user.institution_id).order_by(Case.updated_at.desc())
    if case_id: query = query.where(Case.case_id == case_id)
    if status: query = query.where(Case.status == status)
    return list(db.scalars(query).all())


def get_portal_case_or_404(db: Session, case_id: str, institution_id: int) -> Case:
    case_id_clean = case_id.strip()
    query = select(Case).options(selectinload(Case.institution)).where(Case.institution_id == institution_id)
    if case_id_clean.isdigit():
        query = query.where((Case.id == int(case_id_clean)) | (Case.case_id == case_id_clean))
    else:
        query = query.where(Case.case_id == case_id_clean)
    case = db.scalar(query)
    if not case:
        raise HTTPException(status_code=404, detail="Application not found")
    return case


@router.get("/applications/{case_id}")
def application_detail(case_id: str, db: Session = Depends(get_db), user: User = Depends(representative)) -> dict:
    case = get_portal_case_or_404(db, case_id, user.institution_id)
    history = db.scalars(select(CaseEvent).where(CaseEvent.case_id == case.id).order_by(CaseEvent.created_at)).all()
    alerts = db.scalars(select(Alert).where(Alert.case_id == case.id).order_by(Alert.created_at.desc())).all()
    return {"case": CasePublic.model_validate(case), "institution": InstitutionPublic.model_validate(case.institution), "history": [CaseEventPublic.model_validate(item) for item in history], "alerts": [AlertPublic.model_validate(item) for item in alerts]}


@router.post("/applications/{case_id}/respond")
def respond_to_application(case_id: str, payload: PortalResponseCreate, db: Session = Depends(get_db), user: User = Depends(representative)) -> dict:
    case = get_portal_case_or_404(db, case_id, user.institution_id)
    remarks = payload.remarks.strip()
    case.last_action = remarks
    case.last_action_at = now()
    old_status = case.status
    if case.status == CaseStatus.PENDING_INSTITUTION_RESPONSE:
        case.status = CaseStatus.UNDER_PROCESS
        append_event(db, case, user, ActionType.STATUS_CHANGED, f"Institution response submitted: {remarks}", previous={"status": old_status.value}, new={"status": case.status.value})
    else:
        append_event(db, case, user, ActionType.NOTE, remarks)
    audit(db, user, "case", case.case_id, "institution_response", {"remarks": remarks, "status": case.status.value})
    db.commit()
    db.refresh(case)
    return {"status": "ok", "case_id": case.case_id, "new_status": case.status.value, "message": "Response submitted successfully"}


@router.get("/alerts", response_model=list[AlertPublic])
def portal_alerts(db: Session = Depends(get_db), user: User = Depends(representative)) -> list[Alert]:
    return list(db.scalars(
        select(Alert)
        .join(Case)
        .options(selectinload(Alert.case))
        .where(Case.institution_id == user.institution_id)
        .order_by(Alert.created_at.desc())
    ).all())


@router.get("/documents")
def portal_documents(db: Session = Depends(get_db), user: User = Depends(representative)) -> list[dict]:
    cases = list(db.scalars(select(Case).where(Case.institution_id == user.institution_id).order_by(Case.updated_at.desc())).all())
    docs = []
    for c in cases:
        docs.append({
            "case_id": c.case_id,
            "category": c.category,
            "external_reference": c.external_reference or "N/A",
            "submission_date": str(c.receipt_date),
            "status": c.status.value,
            "document_type": f"{c.category} Docket",
            "access_tier": "Institution Authorized",
        })
    return docs


@router.get("/institution", response_model=InstitutionPublic)
def portal_institution(db: Session = Depends(get_db), user: User = Depends(representative)) -> Institution:
    return db.get(Institution, user.institution_id)
