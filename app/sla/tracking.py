"""
SLA Tracking and Lifecycle Engine for AICTE CaseConnect.

Handles SLA record creation on complaint acceptance, deterministic deadline
calculation, pause/resume state machine, completion performance recording,
and audit logging.
"""
from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import CaseStatus, SlaStatus
from app.intelligence import audit
from app.models import Case, CaseSlaRecord, SlaEvent, SlaPause, SlaPolicy, User
from app.sla.calendar import calculate_deadline, calculate_metrics, ensure_utc
from app.sla.policy_engine import now_utc, resolve_policy

VALID_PAUSE_REASONS = [
    "Awaiting Institutional Clarification / Response",
    "Pending Expert Committee / Scrutiny Inspection",
    "Court Stay / Legal Proceedings",
    "Inter-Bureau Jurisdiction Determination",
    "Official Document Verification in Progress",
    "External Regulatory Review",
    "Other Administrative Requirement",
]


def create_sla_record_for_case(
    db: Session,
    case: Case,
    actor: User | None = None,
    explicit_policy: SlaPolicy | None = None,
) -> CaseSlaRecord | None:
    """
    Create SLA tracking record for an accepted complaint case.
    Does not activate for unaccepted/draft submissions.
    """
    # Check if record already exists
    existing = db.scalar(select(CaseSlaRecord).where(CaseSlaRecord.case_id == case.id))
    if existing:
        return existing

    # Resolve policy
    policy = explicit_policy or resolve_policy(
        db,
        category=case.category,
        priority=case.priority,
        bureau_id=case.current_bureau_id,
        at_time=case.receipt_at,
    )
    if not policy:
        return None

    # Calculate start time and deadlines
    # Use receipt_at or receipt_date as SLA start timestamp
    if case.receipt_at:
        start_time = ensure_utc(case.receipt_at)
    else:
        start_time = ensure_utc(datetime.combine(case.receipt_date, time.min))

    original_deadline = calculate_deadline(start_time, policy.target_duration_days, policy.calendar_type)
    current_deadline = original_deadline

    # Initial metrics
    current_now = now_utc()
    elapsed_h, remaining_h, consumed_pct = calculate_metrics(
        start_time=start_time,
        current_deadline=current_deadline,
        target_duration_days=policy.target_duration_days,
        calendar_type=policy.calendar_type,
        accumulated_paused_seconds=0,
        is_paused=False,
        now_time=current_now,
    )

    # Status determination
    is_terminal = case.status in {CaseStatus.DISPOSED, CaseStatus.CLOSED}
    is_historical_anomaly = start_time.year < 2000
    if is_terminal:
        completion_time = ensure_utc(case.closure_date or case.last_action_at or current_now)
        completed_within_sla = completion_time <= current_deadline
        actual_duration_hours = round(max(0.0, (completion_time - start_time).total_seconds() / 3600.0), 2)
        status_val = SlaStatus.COMPLETED.value
    elif is_historical_anomaly:
        # Pre-policy historical date anomaly: initialize as PAUSED to exclude from operational breach metrics
        status_val = SlaStatus.PAUSED.value
        completion_time = None
        completed_within_sla = None
        actual_duration_hours = None
    elif consumed_pct >= 100.0:
        status_val = SlaStatus.BREACHED.value
        completion_time = None
        completed_within_sla = None
        actual_duration_hours = None
    elif consumed_pct >= policy.at_risk_threshold_pct:
        status_val = SlaStatus.AT_RISK.value
        completion_time = None
        completed_within_sla = None
        actual_duration_hours = None
    elif consumed_pct >= policy.warning_threshold_pct:
        status_val = SlaStatus.WARNING.value
        completion_time = None
        completed_within_sla = None
        actual_duration_hours = None
    else:
        status_val = SlaStatus.ON_TRACK.value
        completion_time = None
        completed_within_sla = None
        actual_duration_hours = None

    record = CaseSlaRecord(
        case_id=case.id,
        case_ref=case.case_id,
        policy_id=policy.id,
        policy_version=policy.version,
        start_time=start_time,
        original_deadline=original_deadline,
        current_deadline=current_deadline,
        target_duration_days=policy.target_duration_days,
        calendar_type=policy.calendar_type.value if hasattr(policy.calendar_type, "value") else str(policy.calendar_type),
        status=status_val,
        elapsed_duration_hours=0.0 if is_historical_anomaly else elapsed_h,
        remaining_duration_hours=0.0 if is_historical_anomaly else remaining_h,
        consumed_percentage=0.0 if is_historical_anomaly else consumed_pct,
        accumulated_paused_seconds=0,
        is_paused=is_historical_anomaly,
        completion_time=completion_time,
        completed_within_sla=completed_within_sla,
        actual_duration_hours=actual_duration_hours,
        escalation_level=0,
        last_evaluated_at=current_now,
    )
    db.add(record)
    db.flush()

    # Record event
    event = SlaEvent(
        sla_record_id=record.id,
        case_id=case.id,
        event_type="CREATED",
        actor_id=actor.id if actor else None,
        previous_state=None,
        new_state={
            "policy_id": policy.id,
            "policy_name": policy.name,
            "target_duration_days": policy.target_duration_days,
            "current_deadline": current_deadline.isoformat(),
            "status": status_val,
            "is_paused": is_historical_anomaly,
        },
        remarks=(
            "SLA tracking initialized in PAUSED state: Pre-policy historical date anomaly (year < 2000) pending date verification"
            if is_historical_anomaly
            else f"SLA tracking activated under policy '{policy.name}'"
        ),
    )
    db.add(event)
    audit(
        db,
        actor,
        "case_sla",
        str(case.id),
        "sla_activated",
        {"policy_id": policy.id, "deadline": current_deadline.isoformat(), "status": status_val},
    )
    db.commit()
    db.refresh(record)
    return record


def pause_sla(
    db: Session,
    case: Case,
    reason: str,
    notes: str | None,
    actor: User,
) -> CaseSlaRecord:
    """Pause SLA countdown for an eligible complaint."""
    record = db.scalar(select(CaseSlaRecord).where(CaseSlaRecord.case_id == case.id))
    if not record:
        raise ValueError(f"No active SLA record for case {case.case_id}")
    if record.status == SlaStatus.COMPLETED.value:
        raise ValueError("Cannot pause an SLA that is already completed")
    if record.is_paused:
        raise ValueError("SLA is already paused")

    clean_reason = reason.strip()
    pause_time = now_utc()

    pause = SlaPause(
        sla_record_id=record.id,
        paused_at=pause_time,
        paused_by_id=actor.id,
        pause_reason=clean_reason,
        pause_notes=notes.strip() if notes else None,
    )
    db.add(pause)
    db.flush()

    prev_status = record.status
    record.is_paused = True
    record.current_pause_id = pause.id
    record.status = SlaStatus.PAUSED.value
    record.last_evaluated_at = pause_time

    event = SlaEvent(
        sla_record_id=record.id,
        case_id=case.id,
        event_type="PAUSED",
        actor_id=actor.id,
        previous_state={"status": prev_status, "is_paused": False},
        new_state={"status": SlaStatus.PAUSED.value, "is_paused": True, "pause_reason": clean_reason},
        remarks=notes or f"SLA paused: {clean_reason}",
    )
    db.add(event)
    audit(
        db,
        actor,
        "case_sla",
        str(case.id),
        "sla_paused",
        {"reason": clean_reason, "notes": notes},
    )
    db.commit()
    db.refresh(record)
    return record


def resume_sla(
    db: Session,
    case: Case,
    notes: str | None,
    actor: User,
) -> CaseSlaRecord:
    """Resume a paused SLA and adjust the deadline accordingly."""
    record = db.scalar(select(CaseSlaRecord).where(CaseSlaRecord.case_id == case.id))
    if not record:
        raise ValueError(f"No active SLA record for case {case.case_id}")
    if not record.is_paused:
        raise ValueError("SLA is not paused")

    resume_time = now_utc()
    pause: SlaPause | None = None
    if record.current_pause_id:
        pause = db.get(SlaPause, record.current_pause_id)
    if not pause:
        # Fallback to the latest pause with no resume timestamp
        pause = db.scalar(
            select(SlaPause)
            .where(SlaPause.sla_record_id == record.id, SlaPause.resumed_at.is_(None))
            .order_by(SlaPause.paused_at.desc())
        )

    pause_seconds = 0
    if pause:
        pause.resumed_at = resume_time
        pause.resumed_by_id = actor.id
        pause.resume_notes = notes.strip() if notes else None
        paused_at_utc = ensure_utc(pause.paused_at)
        pause_seconds = max(0, int((resume_time - paused_at_utc).total_seconds()))
        pause.duration_seconds = pause_seconds

    # Adjust deadline forward by pause interval
    record.accumulated_paused_seconds += pause_seconds
    record.current_deadline = ensure_utc(record.current_deadline) + timedelta(seconds=pause_seconds)
    record.is_paused = False
    record.current_pause_id = None

    # Recalculate metrics
    elapsed_h, remaining_h, consumed_pct = calculate_metrics(
        start_time=record.start_time,
        current_deadline=record.current_deadline,
        target_duration_days=record.target_duration_days,
        calendar_type=record.calendar_type,
        accumulated_paused_seconds=record.accumulated_paused_seconds,
        is_paused=False,
        now_time=resume_time,
    )
    record.elapsed_duration_hours = elapsed_h
    record.remaining_duration_hours = remaining_h
    record.consumed_percentage = consumed_pct

    # Determine resumed status
    policy = record.policy
    warning_pct = policy.warning_threshold_pct if policy else 75.0
    at_risk_pct = policy.at_risk_threshold_pct if policy else 90.0

    if consumed_pct >= 100.0:
        record.status = SlaStatus.BREACHED.value
    elif consumed_pct >= at_risk_pct:
        record.status = SlaStatus.AT_RISK.value
    elif consumed_pct >= warning_pct:
        record.status = SlaStatus.WARNING.value
    else:
        record.status = SlaStatus.ON_TRACK.value

    record.last_evaluated_at = resume_time

    event = SlaEvent(
        sla_record_id=record.id,
        case_id=case.id,
        event_type="RESUMED",
        actor_id=actor.id,
        previous_state={"status": SlaStatus.PAUSED.value, "is_paused": True},
        new_state={
            "status": record.status,
            "is_paused": False,
            "new_deadline": record.current_deadline.isoformat(),
            "pause_duration_seconds": pause_seconds,
        },
        remarks=notes or f"SLA resumed after {round(pause_seconds / 3600, 1)}h pause",
    )
    db.add(event)
    audit(
        db,
        actor,
        "case_sla",
        str(case.id),
        "sla_resumed",
        {"new_deadline": record.current_deadline.isoformat(), "pause_seconds": pause_seconds},
    )
    db.commit()
    db.refresh(record)
    return record


def complete_sla(
    db: Session,
    case: Case,
    actor: User | None = None,
) -> CaseSlaRecord | None:
    """Record completion of SLA when complaint reaches terminal Disposed or Closed status."""
    record = db.scalar(select(CaseSlaRecord).where(CaseSlaRecord.case_id == case.id))
    if not record or record.status == SlaStatus.COMPLETED.value:
        return record

    completion_time = now_utc()
    record.completion_time = completion_time
    record.status = SlaStatus.COMPLETED.value
    record.completed_within_sla = bool(completion_time <= ensure_utc(record.current_deadline))

    # Calculate actual resolution duration in hours (excluding pause time)
    gross_seconds = (completion_time - ensure_utc(record.start_time)).total_seconds()
    net_seconds = max(0.0, gross_seconds - record.accumulated_paused_seconds)
    record.actual_duration_hours = round(net_seconds / 3600.0, 2)
    record.last_evaluated_at = completion_time

    event = SlaEvent(
        sla_record_id=record.id,
        case_id=case.id,
        event_type="COMPLETED",
        actor_id=actor.id if actor else None,
        previous_state={"status": record.status},
        new_state={
            "status": SlaStatus.COMPLETED.value,
            "completed_within_sla": record.completed_within_sla,
            "actual_duration_hours": record.actual_duration_hours,
        },
        remarks=f"Case completed. Within SLA: {'Yes' if record.completed_within_sla else 'No'}",
    )
    db.add(event)
    audit(
        db,
        actor,
        "case_sla",
        str(case.id),
        "sla_completed",
        {"within_sla": record.completed_within_sla, "duration_hours": record.actual_duration_hours},
    )
    db.commit()
    db.refresh(record)
    return record


def recalculate_sla(
    db: Session,
    case: Case,
    new_policy: SlaPolicy | None = None,
    reason: str | None = None,
    actor: User | None = None,
) -> CaseSlaRecord:
    """Administratively recalculate SLA deadline with an updated or explicit policy."""
    record = db.scalar(select(CaseSlaRecord).where(CaseSlaRecord.case_id == case.id))
    if not record:
        raise ValueError(f"No active SLA record for case {case.case_id}")

    policy = new_policy or record.policy
    prev_deadline = record.current_deadline
    start_time = ensure_utc(record.start_time)

    # Calculate new nominal deadline
    nominal_deadline = calculate_deadline(start_time, policy.target_duration_days, policy.calendar_type)
    # Add accumulated paused duration
    adjusted_deadline = nominal_deadline + timedelta(seconds=record.accumulated_paused_seconds)

    record.policy_id = policy.id
    record.policy_version = policy.version
    record.target_duration_days = policy.target_duration_days
    record.calendar_type = policy.calendar_type.value if hasattr(policy.calendar_type, "value") else str(policy.calendar_type)
    record.current_deadline = adjusted_deadline

    # Recalculate metrics
    elapsed_h, remaining_h, consumed_pct = calculate_metrics(
        start_time=start_time,
        current_deadline=adjusted_deadline,
        target_duration_days=policy.target_duration_days,
        calendar_type=policy.calendar_type,
        accumulated_paused_seconds=record.accumulated_paused_seconds,
        is_paused=record.is_paused,
    )
    record.elapsed_duration_hours = elapsed_h
    record.remaining_duration_hours = remaining_h
    record.consumed_percentage = consumed_pct

    if not record.is_paused and record.status != SlaStatus.COMPLETED.value:
        if consumed_pct >= 100.0:
            record.status = SlaStatus.BREACHED.value
        elif consumed_pct >= policy.at_risk_threshold_pct:
            record.status = SlaStatus.AT_RISK.value
        elif consumed_pct >= policy.warning_threshold_pct:
            record.status = SlaStatus.WARNING.value
        else:
            record.status = SlaStatus.ON_TRACK.value

    record.last_evaluated_at = now_utc()

    event = SlaEvent(
        sla_record_id=record.id,
        case_id=case.id,
        event_type="DEADLINE_RECALCULATED",
        actor_id=actor.id if actor else None,
        previous_state={"deadline": prev_deadline.isoformat(), "policy_id": record.policy_id},
        new_state={"deadline": adjusted_deadline.isoformat(), "policy_id": policy.id, "status": record.status},
        remarks=reason or "Deadline administratively recalculated",
    )
    db.add(event)
    audit(
        db,
        actor,
        "case_sla",
        str(case.id),
        "sla_recalculated",
        {"previous_deadline": prev_deadline.isoformat(), "new_deadline": adjusted_deadline.isoformat()},
        reason,
    )
    db.commit()
    db.refresh(record)
    return record

