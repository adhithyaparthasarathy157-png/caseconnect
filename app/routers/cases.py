from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import can_modify_case, can_view_case, get_current_user
from app.enums import CaseStatus
from app.models import (
    Alert,
    Case,
    CaseEvent,
    CoordinationRequest,
    Institution,
    OverlapCandidate,
    User,
)
from app.schemas import (
    AlertPublic,
    CaseActionCreate,
    CaseContext,
    CaseCreate,
    CaseEventPublic,
    CasePublic,
    CaseUpdate,
    CoordinationPublic,
    OverlapPublic,
    PaginatedCases,
)
from app.services import apply_action, can_create_for_bureaus, create_case, update_case

router = APIRouter(prefix="/api/cases", tags=["cases"])


def get_case_or_404(db: Session, case_id: str) -> Case:
    case = db.scalar(select(Case).options(selectinload(Case.institution)).where(Case.case_id == case_id))
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.get("", response_model=PaginatedCases)
def list_cases(institution_id: int | None = None, permanent_id: str | None = None, case_id: str | None = None,
               bureau_id: int | None = None, region: str | None = None, category: str | None = None,
               case_status: CaseStatus | None = Query(default=None, alias="status"), assigned_officer_id: int | None = None,
               receipt_from: datetime | None = None, receipt_to: datetime | None = None, page: int = Query(1, ge=1),
               page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> PaginatedCases:
    query = select(Case).join(Institution).options(selectinload(Case.institution))
    if institution_id is not None: query = query.where(Case.institution_id == institution_id)
    if permanent_id: query = query.where(Institution.permanent_id == permanent_id)
    if case_id: query = query.where(Case.case_id == case_id)
    if bureau_id is not None: query = query.where(Case.current_bureau_id == bureau_id)
    if region: query = query.where(Institution.region == region)
    if category: query = query.where(Case.category == category)
    if case_status: query = query.where(Case.status == case_status)
    if assigned_officer_id is not None: query = query.where(Case.assigned_officer_id == assigned_officer_id)
    if receipt_from: query = query.where(Case.receipt_at >= receipt_from)
    if receipt_to: query = query.where(Case.receipt_at <= receipt_to)
    candidates = list(db.scalars(query.order_by(Case.receipt_at.desc())).all())
    visible = [case for case in candidates if can_view_case(user, case)]
    start = (page - 1) * page_size
    return PaginatedCases(items=visible[start:start + page_size], total=len(visible), page=page, page_size=page_size)


@router.post("", response_model=CasePublic, status_code=status.HTTP_201_CREATED)
def new_case(payload: CaseCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Case:
    institution = db.get(Institution, payload.institution_id)
    if not institution:
        raise HTTPException(status_code=404, detail="Institution not found")
    current_bureau_id = payload.current_bureau_id or payload.originating_bureau_id
    if not can_create_for_bureaus(user, payload.originating_bureau_id, current_bureau_id, institution):
        raise HTTPException(status_code=403, detail="You cannot create a case for that bureau")
    return create_case(db, payload, user)


@router.get("/{case_id}", response_model=CasePublic)
def get_case(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Case:
    case = get_case_or_404(db, case_id)
    if not can_view_case(user, case):
        raise HTTPException(status_code=403, detail="Case is outside your access scope")
    return case


@router.get("/{case_id}/context", response_model=CaseContext)
def case_context(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> CaseContext:
    case = get_case_or_404(db, case_id)
    if not can_view_case(user, case):
        raise HTTPException(status_code=403, detail="Case is outside your access scope")
    history = list(db.scalars(select(CaseEvent).where(CaseEvent.case_id == case.id).order_by(CaseEvent.created_at)).all())
    candidates = db.scalars(
        select(OverlapCandidate).options(
            selectinload(OverlapCandidate.case_low).selectinload(Case.institution),
            selectinload(OverlapCandidate.case_high).selectinload(Case.institution),
        ).where((OverlapCandidate.case_low_id == case.id) | (OverlapCandidate.case_high_id == case.id))
    ).all()
    visible_overlaps = [item for item in candidates if can_view_case(user, item.case_low) and can_view_case(user, item.case_high)]
    alerts = list(db.scalars(select(Alert).where(Alert.case_id == case.id).order_by(Alert.created_at.desc())).all())
    requests = db.scalars(
        select(CoordinationRequest).options(
            selectinload(CoordinationRequest.requesting_case).selectinload(Case.institution),
            selectinload(CoordinationRequest.receiving_case).selectinload(Case.institution),
        ).where((CoordinationRequest.requesting_case_id == case.id) | (CoordinationRequest.receiving_case_id == case.id))
    ).all()
    visible_requests = [item for item in requests if can_view_case(user, item.requesting_case) and can_view_case(user, item.receiving_case)]
    return CaseContext(
        case=CasePublic.model_validate(case),
        history=[CaseEventPublic.model_validate(item) for item in history],
        overlaps=[OverlapPublic.model_validate(item) for item in visible_overlaps],
        alerts=[AlertPublic.model_validate(item) for item in alerts],
        coordination=[CoordinationPublic.model_validate(item) for item in visible_requests],
    )


@router.patch("/{case_id}", response_model=CasePublic)
def patch_case(case_id: str, payload: CaseUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Case:
    case = get_case_or_404(db, case_id)
    if not can_modify_case(user, case):
        raise HTTPException(status_code=403, detail="You cannot modify this case")
    return update_case(db, case, payload, user)


@router.get("/{case_id}/history", response_model=list[CaseEventPublic])
def case_history(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[CaseEvent]:
    case = get_case_or_404(db, case_id)
    if not can_view_case(user, case):
        raise HTTPException(status_code=403, detail="Case is outside your access scope")
    return list(db.scalars(select(CaseEvent).where(CaseEvent.case_id == case.id).order_by(CaseEvent.created_at)).all())


@router.post("/{case_id}/actions", response_model=CasePublic)
def case_action(case_id: str, payload: CaseActionCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Case:
    case = get_case_or_404(db, case_id)
    if not can_modify_case(user, case):
        raise HTTPException(status_code=403, detail="You cannot modify this case")
    return apply_action(db, case, payload, user)
