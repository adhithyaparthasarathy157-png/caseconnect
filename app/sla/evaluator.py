"""
Automated SLA Evaluation, Reminders and Escalation Engine for AICTE CaseConnect.

Evaluates live SLA records, triggers automated warnings/alerts, and creates
idempotent escalations across configurable thresholds:
- 75% Consumed: Warning reminder to assigned officer
- 90% Consumed: At-risk alert & Level 1 escalation to Bureau Coordinator
- 100% Consumed: Breach notice & Level 2 escalation to Senior Management
- 3 Days Overdue: Level 3 escalation to Competent Authority
- 7 Days Overdue: Level 4 escalation for Higher-Level Administrative Review
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.enums import AlertSeverity, CaseStatus, SlaStatus
from app.intelligence import audit, create_alert
from app.models import Case, CaseSlaRecord, SlaEscalation, SlaEvent, SlaPolicy, User
from app.sla.calendar import calculate_metrics, ensure_utc
from app.sla.policy_engine import now_utc, resolve_policy, seed_demo_policies
from app.sla.tracking import complete_sla, create_sla_record_for_case

logger = logging.getLogger("caseconnect.sla.evaluator")


def _has_escalation_level(db: Session, record_id: int, level: int) -> bool:
    """Check if an escalation for this record and level has already been triggered."""
    existing = db.scalar(
        select(SlaEscalation.id).where(
            SlaEscalation.sla_record_id == record_id,
            SlaEscalation.escalation_level == level,
        )
    )
    return bool(existing)


def _trigger_escalation(
    db: Session,
    record: CaseSlaRecord,
    level: int,
    trigger_type: str,
    target_role: str,
    reason: str,
    eval_time: datetime,
) -> SlaEscalation | None:
    """Idempotently trigger an escalation and emit an SLA event."""
    if _has_escalation_level(db, record.id, level):
        return None

    escalation = SlaEscalation(
        sla_record_id=record.id,
        case_id=record.case_id,
        escalation_level=level,
        trigger_type=trigger_type,
        previous_authority_id=record.case.assigned_officer_id if record.case else None,
        new_authority_id=None,
        target_bureau_id=record.case.current_bureau_id if record.case else None,
        target_role=target_role,
        reason=reason,
        acknowledged=False,
        created_at=eval_time,
    )
    db.add(escalation)
    db.flush()

    record.escalation_level = max(record.escalation_level, level)

    event = SlaEvent(
        sla_record_id=record.id,
        case_id=record.case_id,
        event_type="ESCALATED",
        actor_id=None,
        previous_state={"escalation_level": record.escalation_level - 1 if record.escalation_level > 0 else 0},
        new_state={"escalation_level": level, "target_role": target_role, "trigger": trigger_type},
        remarks=f"Level {level} escalation triggered: {reason}",
        created_at=eval_time,
    )
    db.add(event)

    audit(
        db,
        None,
        "sla_escalation",
        str(escalation.id),
        "sla_escalation_triggered",
        {"case_id": record.case_id, "level": level, "trigger": trigger_type},
        reason,
    )
    return escalation


def evaluate_sla_record(
    db: Session,
    record: CaseSlaRecord,
    eval_time: datetime | None = None,
) -> dict[str, Any]:
    """
    Evaluate a single SLA record, update status and trigger reminders/escalations.
    """
    current_now = eval_time or now_utc()
    case = record.case

    # If case has reached terminal status, complete SLA
    if case and case.status in {CaseStatus.DISPOSED, CaseStatus.CLOSED}:
        if record.status != SlaStatus.COMPLETED.value:
            complete_sla(db, case)
        return {"status": record.status, "action": "completed"}

    # If currently paused, do not advance elapsed duration
    if record.is_paused:
        record.last_evaluated_at = current_now
        return {"status": SlaStatus.PAUSED.value, "action": "paused"}

    # Calculate metrics
    elapsed_h, remaining_h, consumed_pct = calculate_metrics(
        start_time=record.start_time,
        current_deadline=record.current_deadline,
        target_duration_days=record.target_duration_days,
        calendar_type=record.calendar_type,
        accumulated_paused_seconds=record.accumulated_paused_seconds,
        is_paused=False,
        now_time=current_now,
    )
    record.elapsed_duration_hours = elapsed_h
    record.remaining_duration_hours = remaining_h
    record.consumed_percentage = consumed_pct

    policy = record.policy
    warning_pct = policy.warning_threshold_pct if policy else 75.0
    at_risk_pct = policy.at_risk_threshold_pct if policy else 90.0

    prev_status = record.status
    overdue_days = 0.0
    if remaining_h < 0:
        overdue_days = abs(remaining_h) / 24.0

    # Determine status
    if consumed_pct >= 100.0 or overdue_days > 0:
        new_status = SlaStatus.BREACHED.value
    elif consumed_pct >= at_risk_pct:
        new_status = SlaStatus.AT_RISK.value
    elif consumed_pct >= warning_pct:
        new_status = SlaStatus.WARNING.value
    else:
        new_status = SlaStatus.ON_TRACK.value

    # If status changed, record event
    if new_status != prev_status:
        record.status = new_status
        db.add(
            SlaEvent(
                sla_record_id=record.id,
                case_id=record.case_id,
                event_type="STATUS_CHANGED",
                actor_id=None,
                previous_state={"status": prev_status},
                new_state={"status": new_status, "consumed_pct": consumed_pct},
                remarks=f"Status updated from {prev_status} to {new_status} ({consumed_pct}% consumed)",
                created_at=current_now,
            )
        )

    # 1. Warning Alert (75%)
    if consumed_pct >= warning_pct:
        create_alert(
            db,
            key=f"sla:warning:{record.id}:{record.policy_version}",
            alert_type="sla_warning",
            severity=AlertSeverity.WARNING,
            title="SLA Warning - 75% Time Consumed",
            message=f"Case {record.case_ref} has consumed {round(consumed_pct)}% of SLA target duration. Deadline approaching.",
            case=case,
        )

    # 2. At-Risk Alert & Level 1 Escalation (90%)
    if consumed_pct >= at_risk_pct:
        create_alert(
            db,
            key=f"sla:at_risk:{record.id}:{record.policy_version}",
            alert_type="sla_at_risk",
            severity=AlertSeverity.CRITICAL,
            title="SLA At Risk - 90% Time Consumed",
            message=f"Case {record.case_ref} is at immediate risk of SLA breach ({round(consumed_pct)}% consumed).",
            case=case,
        )
        _trigger_escalation(
            db,
            record=record,
            level=1,
            trigger_type="at_risk_threshold",
            target_role="Bureau Coordinator",
            reason=f"SLA consumed {round(consumed_pct)}% - escalation to Bureau Coordinator for expedited resolution",
            eval_time=current_now,
        )

    # 3. Breach Alert & Level 2 Escalation (100%)
    if consumed_pct >= 100.0:
        create_alert(
            db,
            key=f"sla:breach:{record.id}:{record.policy_version}",
            alert_type="sla_breached",
            severity=AlertSeverity.CRITICAL,
            title="SLA Breached - Target Deadline Passed",
            message=f"Case {record.case_ref} has breached SLA deadline of {record.current_deadline.strftime('%d-%m-%Y')}.",
            case=case,
        )
        _trigger_escalation(
            db,
            record=record,
            level=2,
            trigger_type="breach_threshold",
            target_role="Senior Management",
            reason=f"Target SLA deadline breached on {record.current_deadline.strftime('%d-%m-%Y')} - escalated to Senior Management",
            eval_time=current_now,
        )

    # 4. Overdue >= 3 Days: Level 3 Escalation
    if overdue_days >= 3.0:
        _trigger_escalation(
            db,
            record=record,
            level=3,
            trigger_type="overdue_days_3",
            target_role="Competent Authority",
            reason=f"Case is {round(overdue_days, 1)} days overdue past SLA deadline - escalated to Competent Authority",
            eval_time=current_now,
        )

    # 5. Overdue >= 7 Days: Level 4 Escalation
    if overdue_days >= 7.0:
        _trigger_escalation(
            db,
            record=record,
            level=4,
            trigger_type="overdue_days_7",
            target_role="System Administrator / Review Board",
            reason=f"Critical SLA pendency: {round(overdue_days, 1)} days overdue - higher-level administrative review triggered",
            eval_time=current_now,
        )

    record.last_evaluated_at = current_now
    return {
        "status": record.status,
        "consumed_pct": consumed_pct,
        "remaining_hours": remaining_h,
        "overdue_days": overdue_days,
        "escalation_level": record.escalation_level,
    }


def evaluate_all_active(db: Session) -> dict[str, int]:
    """
    Run evaluation across all active SLA records.
    Safe and idempotent.
    """
    records = list(
        db.scalars(
            select(CaseSlaRecord)
            .options(selectinload(CaseSlaRecord.case).selectinload(Case.institution), selectinload(CaseSlaRecord.policy))
            .where(CaseSlaRecord.status != SlaStatus.COMPLETED.value)
        ).all()
    )

    counts = {"evaluated": len(records), "warnings": 0, "at_risk": 0, "breached": 0, "escalations": 0}
    current_now = now_utc()

    for rec in records:
        try:
            prev_esc = rec.escalation_level
            res = evaluate_sla_record(db, rec, current_now)
            st = rec.status
            if st == SlaStatus.WARNING.value:
                counts["warnings"] += 1
            elif st == SlaStatus.AT_RISK.value:
                counts["at_risk"] += 1
            elif st == SlaStatus.BREACHED.value:
                counts["breached"] += 1
            if rec.escalation_level > prev_esc:
                counts["escalations"] += 1
        except Exception:
            logger.exception("Error evaluating SLA record %s for case %s; continuing remaining records", getattr(rec, "id", None), getattr(rec, "case_ref", None))

    db.commit()
    return counts


def sync_existing_cases_sla(db: Session, actor: User | None = None) -> dict[str, int]:
    """
    Initial backfill / sync for cases in the database that do not yet have an SLA record.
    Safe: does NOT alter existing cases, statuses, or institutions.
    """
    # Ensure baseline policies exist
    seed_demo_policies(db, actor=actor)

    cases = list(
        db.scalars(
            select(Case)
            .options(selectinload(Case.institution))
            .order_by(Case.id)
        ).all()
    )

    created_count = 0
    for c in cases:
        rec = db.scalar(select(CaseSlaRecord).where(CaseSlaRecord.case_id == c.id))
        if not rec:
            new_rec = create_sla_record_for_case(db, c, actor=actor)
            if new_rec:
                created_count += 1

    # Run evaluation on newly created and active records
    eval_res = evaluate_all_active(db)
    return {
        "cases_total": len(cases),
        "records_created": created_count,
        "active_evaluated": eval_res["evaluated"],
    }

