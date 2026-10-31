from datetime import UTC, datetime, time

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import ActionType, AlertSeverity, CaseStatus, Role
from app.intelligence import audit, create_alert
from app.models import Bureau, Case, CaseEvent, Institution, User
from app.schemas import CaseActionCreate, CaseCreate, CaseUpdate

TRANSITIONS: dict[CaseStatus, set[CaseStatus]] = {
    CaseStatus.RECEIVED: {CaseStatus.UNDER_REVIEW, CaseStatus.TRANSFERRED, CaseStatus.ESCALATED},
    CaseStatus.UNDER_REVIEW: {CaseStatus.UNDER_PROCESS, CaseStatus.PENDING_INSTITUTION_RESPONSE, CaseStatus.TRANSFERRED, CaseStatus.ESCALATED, CaseStatus.CLOSED},
    CaseStatus.UNDER_PROCESS: {CaseStatus.PENDING_INSTITUTION_RESPONSE, CaseStatus.TRANSFERRED, CaseStatus.ESCALATED, CaseStatus.DISPOSED, CaseStatus.CLOSED},
    CaseStatus.PENDING_INSTITUTION_RESPONSE: {CaseStatus.UNDER_PROCESS, CaseStatus.TRANSFERRED, CaseStatus.ESCALATED, CaseStatus.DISPOSED, CaseStatus.CLOSED},
    CaseStatus.TRANSFERRED: {CaseStatus.UNDER_REVIEW, CaseStatus.UNDER_PROCESS, CaseStatus.ESCALATED},
    CaseStatus.ESCALATED: {CaseStatus.UNDER_REVIEW, CaseStatus.UNDER_PROCESS, CaseStatus.PENDING_INSTITUTION_RESPONSE, CaseStatus.DISPOSED, CaseStatus.CLOSED},
    CaseStatus.DISPOSED: {CaseStatus.CLOSED},
    CaseStatus.CLOSED: set(),
}


def now() -> datetime:
    return datetime.now(UTC)


def normalize_name(name: str) -> str:
    return " ".join(name.casefold().split())


def unique_case_id(db: Session) -> str:
    year = now().year
    sequence = db.scalar(select(Case.id).order_by(Case.id.desc()).limit(1)) or 0
    candidate = f"CC-{year}-{sequence + 1:05d}"
    while db.scalar(select(Case.id).where(Case.case_id == candidate)):
        sequence += 1
        candidate = f"CC-{year}-{sequence + 1:05d}"
    return candidate


def validate_case_references(db: Session, institution_id: int, origin_id: int, current_id: int, officer_id: int | None) -> None:
    if not db.get(Institution, institution_id):
        raise HTTPException(status_code=404, detail="Institution not found")
    if not db.get(Bureau, origin_id) or not db.get(Bureau, current_id):
        raise HTTPException(status_code=422, detail="Originating and current bureaus must exist")
    if officer_id is not None:
        officer = db.get(User, officer_id)
        if not officer or not officer.is_active:
            raise HTTPException(status_code=422, detail="Assigned officer does not exist or is inactive")
        if officer.bureau_id != current_id:
            raise HTTPException(status_code=422, detail="Assigned officer must belong to the current bureau")


def append_event(db: Session, case: Case, actor: User, action: ActionType, remarks: str | None = None,
                 previous: dict | None = None, new: dict | None = None) -> None:
    db.add(CaseEvent(case_id=case.id, action_type=action, actor_id=actor.id, bureau_id=actor.bureau_id,
                     previous_values=previous, new_values=new, remarks=remarks))


def create_case(db: Session, payload: CaseCreate, actor: User) -> Case:
    current_bureau_id = payload.current_bureau_id or payload.originating_bureau_id
    validate_case_references(db, payload.institution_id, payload.originating_bureau_id, current_bureau_id, payload.assigned_officer_id)
    created = now()
    # The database still retains `receipt_at` for historical reporting.  Its
    # midnight value is an internal date compatibility marker, not a received
    # time or timezone supplied by the user.
    receipt_at = datetime.combine(payload.receipt_date, time.min)
    case = Case(case_id=unique_case_id(db), external_reference=payload.external_reference,
                institution_id=payload.institution_id, receipt_at=receipt_at, receipt_date=payload.receipt_date, source_channel=payload.source_channel,
                category=payload.category, subcategory=payload.subcategory, subject=payload.subject,
                description=payload.description, priority=payload.priority, originating_bureau_id=payload.originating_bureau_id,
                current_bureau_id=current_bureau_id, assigned_officer_id=payload.assigned_officer_id,
                status=CaseStatus.RECEIVED, last_action="Case received", last_action_at=created,
                next_action=payload.next_action, expected_disposal_date=payload.expected_disposal_date)
    db.add(case)
    db.flush()
    try:
        from app.sla.tracking import create_sla_record_for_case
        create_sla_record_for_case(db, case, actor=actor)
    except Exception:
        pass
    append_event(db, case, actor, ActionType.CREATED, "Case created", new={"status": case.status.value})
    audit(db, actor, "case", case.case_id, "case_created")
    db.commit()
    db.refresh(case)
    return case


def assert_transition(old: CaseStatus, new: CaseStatus) -> None:
    if old != new and new not in TRANSITIONS[old]:
        raise HTTPException(status_code=422,
                            detail=f"Invalid status transition: {old.value} -> {new.value}")


def update_case(db: Session, case: Case, payload: CaseUpdate, actor: User) -> Case:
    changes = payload.model_dump(exclude_unset=True, exclude={"remarks"})
    if "status" in changes:
        assert_transition(case.status, changes["status"])
    if "assigned_officer_id" in changes and changes["assigned_officer_id"] is not None:
        officer = db.get(User, changes["assigned_officer_id"])
        if not officer or not officer.is_active:
            raise HTTPException(status_code=422, detail="Assigned officer does not exist or is inactive")
        if officer.bureau_id != case.current_bureau_id:
            raise HTTPException(status_code=422, detail="Assigned officer must belong to the current bureau")
    previous = {key: getattr(case, key).value if hasattr(getattr(case, key), "value") else getattr(case, key) for key in changes}
    for key, value in changes.items():
        setattr(case, key, value)
    if "status" in changes and changes["status"] in {CaseStatus.DISPOSED, CaseStatus.CLOSED}:
        case.closure_date = now()
        try:
            from app.sla.tracking import complete_sla
            complete_sla(db, case, actor=actor)
        except Exception:
            pass
    if changes:
        case.last_action = payload.remarks or "Case updated"
        case.last_action_at = now()
        event_action = ActionType.STATUS_CHANGED if "status" in changes else (ActionType.REASSIGNED if "assigned_officer_id" in changes else ActionType.UPDATED)
        new = {key: value.value if hasattr(value, "value") else value for key, value in changes.items()}
        append_event(db, case, actor, event_action, payload.remarks, previous, new)
        audit(db, actor, "case", case.case_id, "case_updated", new, payload.remarks)
        db.commit()
        db.refresh(case)
    return case


def apply_action(db: Session, case: Case, payload: CaseActionCreate, actor: User) -> Case:
    previous: dict = {}
    new: dict = {}
    if payload.action_type == ActionType.TRANSFERRED:
        if not payload.target_bureau_id or not db.get(Bureau, payload.target_bureau_id):
            raise HTTPException(status_code=422, detail="A valid target_bureau_id is required for transfer")
        if payload.target_bureau_id == case.current_bureau_id:
            raise HTTPException(status_code=422, detail="Target bureau must differ from the current bureau")
        assert_transition(case.status, CaseStatus.TRANSFERRED)
        previous = {"current_bureau_id": case.current_bureau_id, "status": case.status.value}
        case.current_bureau_id = payload.target_bureau_id
        case.assigned_officer_id = None
        case.status = CaseStatus.TRANSFERRED
        new = {"current_bureau_id": case.current_bureau_id, "status": case.status.value}
    elif payload.action_type == ActionType.ESCALATED:
        assert_transition(case.status, CaseStatus.ESCALATED)
        previous = {"status": case.status.value}
        case.status = CaseStatus.ESCALATED
        new = {"status": case.status.value}
    elif payload.action_type in {ActionType.ASSIGNED, ActionType.REASSIGNED}:
        officer = db.get(User, payload.assigned_officer_id) if payload.assigned_officer_id else None
        if not officer or not officer.is_active:
            raise HTTPException(status_code=422, detail="A valid active assigned_officer_id is required")
        if officer.bureau_id != case.current_bureau_id:
            raise HTTPException(status_code=422, detail="Assigned officer must belong to the current bureau")
        previous = {"assigned_officer_id": case.assigned_officer_id}
        case.assigned_officer_id = payload.assigned_officer_id
        new = {"assigned_officer_id": case.assigned_officer_id}
    elif payload.action_type == ActionType.STATUS_CHANGED:
        if not payload.status:
            raise HTTPException(status_code=422, detail="A target status is required")
        assert_transition(case.status, payload.status)
        previous = {"status": case.status.value}
        case.status = payload.status
        if case.status in {CaseStatus.DISPOSED, CaseStatus.CLOSED}:
            case.closure_date = now()
            try:
                from app.sla.tracking import complete_sla
                complete_sla(db, case, actor=actor)
            except Exception:
                pass
        new = {"status": case.status.value}
    elif payload.action_type != ActionType.NOTE:
        raise HTTPException(status_code=422, detail="Unsupported workflow action")
    case.last_action = payload.remarks
    case.last_action_at = now()
    append_event(db, case, actor, payload.action_type, payload.remarks, previous or None, new or None)
    audit(db, actor, "case", case.case_id, f"case_{payload.action_type.value}", new or None, payload.remarks)
    if payload.action_type == ActionType.ESCALATED:
        create_alert(db, key=f"escalation:{case.id}", alert_type="escalation", severity=AlertSeverity.WARNING,
                     title="Case escalated", message="A case requires escalated attention.", case=case)
    db.commit()
    db.refresh(case)
    return case


def can_create_for_bureaus(actor: User, originating_bureau_id: int, current_bureau_id: int, institution: Institution) -> bool:
    if actor.role in {Role.ADMIN, Role.COMPETENT_AUTHORITY}:
        return True
    if actor.role == Role.INSTITUTION_REPRESENTATIVE:
        return (
            actor.institution_id == institution.id
            and (actor.bureau_id is None or actor.bureau_id == originating_bureau_id)
            and originating_bureau_id == current_bureau_id
        )
    if actor.role == Role.SENIOR_MANAGEMENT:
        return False
    if actor.bureau_id != originating_bureau_id or actor.bureau_id != current_bureau_id:
        return False
    if actor.role == Role.REGIONAL_OFFICER:
        regions = {item.strip().casefold() for item in (actor.region_scope or "").split(",") if item.strip()}
        return "all" in regions or institution.region.casefold() in regions
    return True
