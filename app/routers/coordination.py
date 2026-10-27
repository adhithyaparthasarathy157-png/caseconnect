"""Human cross-bureau coordination for existing overlap candidates.

Requests are advisory.  They never transfer, merge, close, or otherwise alter
either case solely because a potential overlap exists.
"""
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import can_modify_case, can_view_case, get_current_user, is_broad_viewer
from app.enums import AlertSeverity, CoordinationStatus, OverlapStatus, Role
from app.intelligence import audit, create_alert
from app.models import Case, CoordinationRequest, OverlapCandidate, User
from app.schemas import CoordinationCreate, CoordinationPublic, CoordinationResponse

router = APIRouter(prefix="/api/coordination", tags=["coordination"])


def _request_query():
    return select(CoordinationRequest).options(
        selectinload(CoordinationRequest.requesting_case).selectinload(Case.institution),
        selectinload(CoordinationRequest.receiving_case).selectinload(Case.institution),
    )


def visible(user: User, request: CoordinationRequest) -> bool:
    if is_broad_viewer(user):
        return True
    if user.bureau_id == request.requesting_bureau_id:
        return can_view_case(user, request.requesting_case)
    if user.bureau_id == request.receiving_bureau_id:
        return can_view_case(user, request.receiving_case)
    # Regional users retain their existing case-level, rather than bureau-level,
    # scope. A coordination reference grants no additional data access.
    return can_view_case(user, request.requesting_case) and can_view_case(user, request.receiving_case)


def get_request_or_404(db: Session, request_id: str) -> CoordinationRequest:
    request = db.scalar(_request_query().where(CoordinationRequest.id == request_id))
    if not request:
        raise HTTPException(status_code=404, detail="Coordination request not found")
    return request


@router.get("", response_model=list[CoordinationPublic])
def list_requests(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[CoordinationRequest]:
    requests = db.scalars(_request_query().order_by(CoordinationRequest.created_at.desc())).all()
    return [request for request in requests if visible(user, request)]


@router.get("/{request_id}", response_model=CoordinationPublic)
def get_request(request_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> CoordinationRequest:
    request = get_request_or_404(db, request_id)
    if not visible(user, request):
        raise HTTPException(status_code=403, detail="Coordination request is outside your access scope")
    return request


@router.post("/from-overlap/{overlap_id}", response_model=CoordinationPublic, status_code=status.HTTP_201_CREATED)
def create_request(overlap_id: int, payload: CoordinationCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> CoordinationRequest:
    candidate = db.scalar(
        select(OverlapCandidate).options(
            selectinload(OverlapCandidate.case_low).selectinload(Case.institution),
            selectinload(OverlapCandidate.case_high).selectinload(Case.institution),
        ).where(OverlapCandidate.id == overlap_id)
    )
    if not candidate:
        raise HTTPException(status_code=404, detail="Overlap candidate not found")
    if not (can_view_case(user, candidate.case_low) and can_view_case(user, candidate.case_high)):
        raise HTTPException(status_code=403, detail="You cannot coordinate this overlap")
    if payload.requesting_case_id == candidate.case_low_id:
        source, target = candidate.case_low, candidate.case_high
    elif payload.requesting_case_id == candidate.case_high_id:
        source, target = candidate.case_high, candidate.case_low
    else:
        raise HTTPException(status_code=422, detail="requesting_case_id must belong to the overlap")
    if not can_modify_case(user, source):
        raise HTTPException(status_code=403, detail="You cannot request coordination for that case")
    if source.current_bureau_id == target.current_bureau_id:
        raise HTTPException(status_code=422, detail="Coordination requires cases in different current bureaus")
    request = CoordinationRequest(
        overlap_id=candidate.id,
        requesting_case_id=source.id,
        receiving_case_id=target.id,
        requesting_bureau_id=source.current_bureau_id,
        receiving_bureau_id=target.current_bureau_id,
        requester_id=user.id,
        reason=payload.reason,
    )
    db.add(request)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A coordination request already exists for this overlap") from exc
    candidate.status = OverlapStatus.COORDINATION_REQUESTED
    candidate.reviewer_id = user.id
    candidate.reviewed_at = datetime.now(UTC)
    candidate.remarks = payload.reason
    create_alert(
        db,
        key=f"coordination:{request.id}",
        alert_type="coordination_requested",
        severity=AlertSeverity.WARNING,
        title="Coordination response requested",
        message="A related case requires cross-bureau coordination.",
        case=target,
        overlap=candidate,
    )
    audit(db, user, "coordination", request.id, "coordination_requested", {
        "overlap_id": candidate.id,
        "requesting_case_id": source.id,
        "receiving_case_id": target.id,
        "requesting_bureau_id": source.current_bureau_id,
        "receiving_bureau_id": target.current_bureau_id,
    }, payload.reason)
    audit(db, user, "overlap", str(candidate.id), "overlap_coordination_requested", {"coordination_id": request.id}, payload.reason)
    db.commit()
    db.refresh(request)
    return request


@router.post("/{request_id}/respond", response_model=CoordinationPublic)
def respond(request_id: str, payload: CoordinationResponse, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> CoordinationRequest:
    request = get_request_or_404(db, request_id)
    if request.status == CoordinationStatus.RESOLVED:
        raise HTTPException(status_code=422, detail="A resolved coordination request cannot be changed")
    if payload.status == CoordinationStatus.PENDING:
        raise HTTPException(status_code=422, detail="A response must change the coordination status")
    recipient_can_respond = user.bureau_id == request.receiving_bureau_id and can_modify_case(user, request.receiving_case)
    if not (user.role in {Role.ADMIN, Role.COMPETENT_AUTHORITY} or recipient_can_respond):
        raise HTTPException(status_code=403, detail="Only the receiving bureau may respond to this coordination request")
    previous = {"status": request.status.value, "response": request.response}
    request.status = payload.status
    request.response = payload.response
    request.responded_by_id = user.id
    request.responded_at = datetime.now(UTC)
    audit(db, user, "coordination", request.id, "coordination_responded", {
        "previous": previous,
        "status": request.status.value,
        "receiving_case_id": request.receiving_case_id,
    }, payload.response)
    db.commit()
    db.refresh(request)
    return request
