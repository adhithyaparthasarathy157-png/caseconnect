from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import can_view_case, get_current_user
from app.enums import Role
from app.intelligence import audit
from app.models import Case, CoordinationRequest, Institution, OverlapCandidate, User
from app.schemas import (
    CasePublic,
    InstitutionCreate,
    InstitutionProfile,
    InstitutionPublic,
    InstitutionRelatedCoordination,
    InstitutionRelatedOverlap,
    InstitutionUpdate,
)
from app.services import normalize_name

router = APIRouter(prefix="/api/institutions", tags=["institutions"])
MANAGERS = {Role.ADMIN, Role.COMPETENT_AUTHORITY}


def get_institution_or_404(db: Session, institution_id: int) -> Institution:
    institution = db.get(Institution, institution_id)
    if not institution:
        raise HTTPException(status_code=404, detail="Institution not found")
    return institution


@router.get("", response_model=list[InstitutionPublic])
def list_institutions(search: str | None = None, permanent_id: str | None = None, region: str | None = None,
                      institution_status: str | None = Query(default=None, alias="status"),
                      db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[Institution]:
    query = select(Institution)
    if search:
        needle = f"%{search.strip()}%"
        query = query.where(or_(Institution.name.ilike(needle), Institution.normalized_name.ilike(needle)))
    if permanent_id:
        query = query.where(Institution.permanent_id == " ".join(permanent_id.split()).upper())
    if region:
        query = query.where(Institution.region == region)
    if institution_status:
        query = query.where(Institution.status == institution_status)
    if user.role == Role.REGIONAL_OFFICER and (user.region_scope or "").upper() != "ALL":
        regions = [item.strip() for item in (user.region_scope or "").split(",") if item.strip()]
        query = query.where(Institution.region.in_(regions))
    return list(db.scalars(query.order_by(Institution.name)).all())


@router.get("/{institution_id}", response_model=InstitutionPublic)
def get_institution(institution_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Institution:
    institution = get_institution_or_404(db, institution_id)
    if user.role == Role.REGIONAL_OFFICER and (user.region_scope or "").upper() not in {"ALL", institution.region.upper()}:
        raise HTTPException(status_code=403, detail="Institution is outside your regional scope")
    return institution


@router.get("/{institution_id}/profile", response_model=InstitutionProfile)
def institution_profile(institution_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> InstitutionProfile:
    institution = get_institution_or_404(db, institution_id)
    if user.role == Role.REGIONAL_OFFICER and (user.region_scope or "").upper() not in {"ALL", institution.region.upper()}:
        raise HTTPException(status_code=403, detail="Institution is outside your regional scope")
    cases = [case for case in db.scalars(select(Case).where(Case.institution_id == institution.id)).all() if can_view_case(user, case)]
    case_ids = {case.id for case in cases}
    candidates = db.scalars(select(OverlapCandidate).where(or_(OverlapCandidate.case_low_id.in_(case_ids or {-1}), OverlapCandidate.case_high_id.in_(case_ids or {-1})))).all()
    related: list[InstitutionRelatedOverlap] = []
    for candidate in candidates:
        left, right = db.get(Case, candidate.case_low_id), db.get(Case, candidate.case_high_id)
        if left and right and can_view_case(user, left) and can_view_case(user, right):
            own, other = (left, right) if left.institution_id == institution.id else (right, left)
            related.append(InstitutionRelatedOverlap(id=candidate.id, case_id=own.case_id, related_case_id=other.case_id, similarity_score=candidate.similarity_score, status=candidate.status, reasons=candidate.reasons))
    requests = db.scalars(
        select(CoordinationRequest).options(
            selectinload(CoordinationRequest.requesting_case).selectinload(Case.institution),
            selectinload(CoordinationRequest.receiving_case).selectinload(Case.institution),
        ).where(
            or_(
                CoordinationRequest.requesting_case_id.in_(case_ids or {-1}),
                CoordinationRequest.receiving_case_id.in_(case_ids or {-1}),
            )
        )
    ).all()
    related_coordination = [
        InstitutionRelatedCoordination(
            id=request.id,
            overlap_id=request.overlap_id,
            requesting_case_id=request.requesting_case_id,
            receiving_case_id=request.receiving_case_id,
            status=request.status,
            reason=request.reason,
            response=request.response,
            responded_at=request.responded_at,
            updated_at=request.updated_at,
        )
        for request in requests
        if can_view_case(user, request.requesting_case) and can_view_case(user, request.receiving_case)
    ]
    base = InstitutionPublic.model_validate(institution).model_dump()
    return InstitutionProfile(**base, total_cases=len(cases), cases_by_status=dict(Counter(case.status.value for case in cases)), cases=[CasePublic.model_validate(case) for case in cases], related_overlaps=related, related_coordination=related_coordination)


@router.post("", response_model=InstitutionPublic, status_code=status.HTTP_201_CREATED)
def create_institution(payload: InstitutionCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Institution:
    if user.role not in MANAGERS:
        raise HTTPException(status_code=403, detail="Only authorized administrators may create institutions")
    institution = Institution(**payload.model_dump(), normalized_name=normalize_name(payload.name))
    db.add(institution)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An institution with this Permanent ID already exists") from exc
    db.refresh(institution)
    audit(db, user, "institution", str(institution.id), "institution_created", {"permanent_id": institution.permanent_id})
    db.commit()
    return institution


@router.patch("/{institution_id}", response_model=InstitutionPublic)
def update_institution(institution_id: int, payload: InstitutionUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Institution:
    if user.role not in MANAGERS:
        raise HTTPException(status_code=403, detail="Only authorized administrators may update institutions")
    institution = get_institution_or_404(db, institution_id)
    updates = payload.model_dump(exclude_unset=True)
    before = {field: getattr(institution, field) for field in updates}
    for field, value in updates.items():
        setattr(institution, field, value)
    if payload.name is not None:
        institution.normalized_name = normalize_name(payload.name)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An institution with this Permanent ID already exists") from exc
    db.refresh(institution)
    after = {field: getattr(institution, field) for field in updates}
    audit(db, user, "institution", str(institution.id), "institution_updated", {"before": before, "after": after})
    db.commit()
    return institution


@router.get("/{institution_id}/cases", response_model=list[CasePublic])
def institution_cases(institution_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[Case]:
    get_institution_or_404(db, institution_id)
    return [case for case in db.scalars(select(Case).where(Case.institution_id == institution_id)).all() if can_view_case(user, case)]
