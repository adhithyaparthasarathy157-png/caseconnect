from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import can_modify_case, can_view_case, get_current_user
from app.enums import OverlapStatus, Role
from app.intelligence import refresh_overlaps, review_overlap
from app.models import Case, OverlapCandidate, User
from app.schemas import OverlapPublic, OverlapReview

router = APIRouter(prefix="/api/overlaps", tags=["overlap review"])


def visible(user: User, candidate: OverlapCandidate) -> bool:
    return can_view_case(user, candidate.case_low) and can_view_case(user, candidate.case_high)


@router.get("", response_model=list[OverlapPublic])
def list_overlaps(status: OverlapStatus | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[OverlapCandidate]:
    query = select(OverlapCandidate).options(selectinload(OverlapCandidate.case_low).selectinload(Case.institution), selectinload(OverlapCandidate.case_high).selectinload(Case.institution))
    if status:
        query = query.where(OverlapCandidate.status == status)
    return [item for item in db.scalars(query.order_by(OverlapCandidate.similarity_score.desc())).all() if visible(user, item)]


@router.post("/refresh")
def refresh(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, int]:
    if user.role not in {Role.ADMIN, Role.COMPETENT_AUTHORITY, Role.SENIOR_MANAGEMENT}:
        raise HTTPException(status_code=403, detail="Only authorized reviewers may refresh overlap suggestions")
    count = refresh_overlaps(db)
    db.commit()
    return {"refreshed": count}


@router.post("/{overlap_id}/review", response_model=OverlapPublic)
def review(overlap_id: int, payload: OverlapReview, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> OverlapCandidate:
    candidate = db.scalar(select(OverlapCandidate).options(selectinload(OverlapCandidate.case_low).selectinload(Case.institution), selectinload(OverlapCandidate.case_high).selectinload(Case.institution)).where(OverlapCandidate.id == overlap_id))
    if not candidate:
        raise HTTPException(status_code=404, detail="Overlap candidate not found")
    if not visible(user, candidate) or (not can_modify_case(user, candidate.case_low) and user.role not in {Role.SENIOR_MANAGEMENT, Role.COMPETENT_AUTHORITY}):
        raise HTTPException(status_code=403, detail="You cannot review this overlap")
    return review_overlap(db, candidate, user, payload.status, payload.remarks)
