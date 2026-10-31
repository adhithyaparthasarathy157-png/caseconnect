"""
SLA and Pendency Performance Analytics for AICTE CaseConnect.

Computes bureau-level, officer-level, and system-wide SLA compliance metrics,
disposal duration averages, overdue distributions, and trends from live database data.
"""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.enums import CaseStatus, Role, SlaStatus
from app.models import Bureau, Case, CaseSlaRecord, SlaEscalation, User
from app.sla.calendar import ensure_utc
from app.sla.schemas import BureauSlaMetric, OfficerSlaMetric, SlaDashboardSummary


def get_dashboard_summary(db: Session, bureau_id: int | None = None) -> SlaDashboardSummary:
    """Compute KPI cards and summary SLA compliance metrics."""
    query = select(CaseSlaRecord).options(selectinload(CaseSlaRecord.case))
    if bureau_id:
        query = query.join(Case).where(Case.current_bureau_id == bureau_id)

    records = list(db.scalars(query).all())

    on_track = 0
    warning = 0
    at_risk = 0
    breached = 0
    paused = 0
    completed = 0
    completed_within_sla = 0

    for r in records:
        st = r.status
        if st == SlaStatus.COMPLETED.value:
            completed += 1
            if r.completed_within_sla:
                completed_within_sla += 1
        elif st == SlaStatus.PAUSED.value:
            paused += 1
        elif st == SlaStatus.BREACHED.value:
            breached += 1
        elif st == SlaStatus.AT_RISK.value:
            at_risk += 1
        elif st == SlaStatus.WARNING.value:
            warning += 1
        elif st == SlaStatus.ON_TRACK.value:
            on_track += 1

    total_active = on_track + warning + at_risk + breached + paused
    # 1. Historical disposal compliance: percentage of closed/disposed cases resolved within SLA
    compliance_pct = round((completed_within_sla / completed * 100.0), 1) if completed > 0 else 100.0

    # 2. Active In-SLA Rate: percentage of active cases currently within target deadline (not breached)
    active_in_sla_pct = round(((total_active - breached) / total_active * 100.0), 1) if total_active > 0 else 100.0

    # 3. Active Healthy Rate: percentage of active cases that are completely on-track or early-warning (not at-risk or breached)
    active_healthy_pct = round(((on_track + warning) / total_active * 100.0), 1) if total_active > 0 else 100.0

    esc_query = select(func.count(SlaEscalation.id))
    if bureau_id:
        esc_query = esc_query.where(SlaEscalation.target_bureau_id == bureau_id)
    total_escalations = db.scalar(esc_query) or 0

    return SlaDashboardSummary(
        total_active_records=total_active,
        on_track_count=on_track,
        warning_count=warning,
        at_risk_count=at_risk,
        breached_count=breached,
        paused_count=paused,
        completed_count=completed,
        completed_within_sla_count=completed_within_sla,
        compliance_percentage=compliance_pct,
        active_compliance_percentage=active_in_sla_pct,
        active_in_sla_percentage=active_in_sla_pct,
        active_healthy_percentage=active_healthy_pct,
        total_escalations_count=total_escalations,
        generated_at=datetime.now(UTC),
    )


def get_bureau_metrics(db: Session) -> list[BureauSlaMetric]:
    """Compute detailed SLA metrics aggregated by bureau/cell."""
    bureaus = list(db.scalars(select(Bureau).order_by(Bureau.id)).all())
    records = list(
        db.scalars(
            select(CaseSlaRecord)
            .options(selectinload(CaseSlaRecord.case))
        ).all()
    )

    # Group by bureau ID
    bureau_records: dict[int, list[CaseSlaRecord]] = defaultdict(list)
    for r in records:
        if r.case and r.case.current_bureau_id:
            bureau_records[r.case.current_bureau_id].append(r)

    # Escalations per bureau
    esc_counts = dict(
        db.execute(
            select(SlaEscalation.target_bureau_id, func.count(SlaEscalation.id))
            .group_by(SlaEscalation.target_bureau_id)
        ).all()
    )

    metrics: list[BureauSlaMetric] = []
    now_dt = datetime.now(UTC)

    for b in bureaus:
        recs = bureau_records.get(b.id, [])
        total = len(recs)
        on_track = sum(1 for r in recs if r.status == SlaStatus.ON_TRACK.value)
        warning = sum(1 for r in recs if r.status == SlaStatus.WARNING.value)
        at_risk = sum(1 for r in recs if r.status == SlaStatus.AT_RISK.value)
        breached = sum(1 for r in recs if r.status == SlaStatus.BREACHED.value)
        paused = sum(1 for r in recs if r.status == SlaStatus.PAUSED.value)
        completed_recs = [r for r in recs if r.status == SlaStatus.COMPLETED.value]
        completed = len(completed_recs)
        pending = total - completed

        within_sla = sum(1 for r in completed_recs if r.completed_within_sla)
        comp_pct = round((within_sla / completed * 100.0), 1) if completed > 0 else 100.0

        # Avg disposal days for completed cases
        durations = [r.actual_duration_hours / 24.0 for r in completed_recs if r.actual_duration_hours is not None]
        avg_disposal = round(sum(durations) / len(durations), 1) if durations else 0.0

        # Avg overdue days for currently breached/active cases
        overdue_days_list = [
            (now_dt - ensure_utc(r.current_deadline)).total_seconds() / 86400.0
            for r in recs
            if r.status == SlaStatus.BREACHED.value and ensure_utc(r.current_deadline) < now_dt
        ]
        avg_overdue = round(sum(overdue_days_list) / len(overdue_days_list), 1) if overdue_days_list else 0.0

        metrics.append(
            BureauSlaMetric(
                bureau_id=b.id,
                bureau_code=b.code,
                bureau_name=b.name,
                total_cases=total,
                pending_cases=pending,
                on_track=on_track,
                warning=warning,
                at_risk=at_risk,
                breached=breached,
                paused=paused,
                completed=completed,
                compliance_percentage=comp_pct,
                avg_disposal_days=avg_disposal,
                avg_overdue_days=avg_overdue,
                escalation_count=esc_counts.get(b.id, 0),
            )
        )

    return metrics


def get_officer_metrics(db: Session, bureau_id: int | None = None) -> list[OfficerSlaMetric]:
    """
    Officer-level SLA metrics. Permission controlled.
    Accounts for workload, completed cases, overdue count, and compliance.
    """
    officer_query = select(User).where(
        User.role.in_([Role.RB_OFFICER, Role.PGRC_OFFICER, Role.OTHER_BUREAU_OFFICER, Role.REGIONAL_OFFICER]),
        User.is_active.is_(True),
    )
    if bureau_id:
        officer_query = officer_query.where(User.bureau_id == bureau_id)
    officers = list(db.scalars(officer_query).all())

    metrics: list[OfficerSlaMetric] = []
    now_dt = datetime.now(UTC)

    for off in officers:
        # Cases assigned to this officer
        cases = list(
            db.scalars(
                select(Case)
                .options(selectinload(Case.sla_record))
                .where(Case.assigned_officer_id == off.id)
            ).all()
        )
        total_assigned = len(cases)
        completed_cases = [c for c in cases if c.status in {CaseStatus.DISPOSED, CaseStatus.CLOSED}]
        pending_cases = total_assigned - len(completed_cases)

        # Overdue
        overdue_count = 0
        within_sla_count = 0
        action_delays_days: list[float] = []

        for c in cases:
            rec = c.sla_record
            if rec:
                if rec.status == SlaStatus.BREACHED.value:
                    overdue_count += 1
                if rec.status == SlaStatus.COMPLETED.value and rec.completed_within_sla:
                    within_sla_count += 1
            if c.last_action_at:
                action_delays_days.append(max(0.0, (now_dt - ensure_utc(c.last_action_at)).total_seconds() / 86400.0))

        comp_pct = round((within_sla_count / len(completed_cases) * 100.0), 1) if completed_cases else 100.0
        avg_delay = round(sum(action_delays_days) / len(action_delays_days), 1) if action_delays_days else 0.0

        bureau_name = off.bureau.name if off.bureau else "Unassigned"
        metrics.append(
            OfficerSlaMetric(
                officer_id=off.id,
                officer_name=off.full_name,
                bureau_name=bureau_name,
                assigned_workload=total_assigned,
                pending_cases=pending_cases,
                completed_cases=len(completed_cases),
                overdue_cases=overdue_count,
                compliance_percentage=comp_pct,
                avg_action_delay_days=avg_delay,
            )
        )

    return sorted(metrics, key=lambda x: x.assigned_workload, reverse=True)


def get_trends(db: Session) -> dict[str, Any]:
    """Monthly compliance trend, category disposal time, and distribution."""
    # 1. Monthly trend (last 6 months)
    records = list(
        db.scalars(
            select(CaseSlaRecord)
            .where(CaseSlaRecord.status == SlaStatus.COMPLETED.value, CaseSlaRecord.completion_time.is_not(None))
        ).all()
    )

    monthly_completed = defaultdict(int)
    monthly_within = defaultdict(int)

    for r in records:
        if r.completion_time:
            key = ensure_utc(r.completion_time).strftime("%b %Y")
            monthly_completed[key] += 1
            if r.completed_within_sla:
                monthly_within[key] += 1

    monthly_trend: list[dict[str, Any]] = []
    # If no historical completed cases in past months, show current month baseline
    current_key = datetime.now(UTC).strftime("%b %Y")
    if not monthly_completed:
        monthly_trend.append({"month": current_key, "compliance_rate": 100.0, "completed": 0, "within_sla": 0})
    else:
        for k in sorted(monthly_completed.keys()):
            tot = monthly_completed[k]
            with_sla = monthly_within[k]
            rate = round((with_sla / tot * 100.0), 1) if tot > 0 else 100.0
            monthly_trend.append({"month": k, "compliance_rate": rate, "completed": tot, "within_sla": with_sla})

    # 2. Category-wise average disposal time
    cases_with_sla = list(
        db.scalars(
            select(Case)
            .options(selectinload(Case.sla_record))
            .where(Case.status.in_([CaseStatus.DISPOSED, CaseStatus.CLOSED]))
        ).all()
    )
    category_durations = defaultdict(list)
    for c in cases_with_sla:
        rec = c.sla_record
        if rec and rec.actual_duration_hours is not None:
            category_durations[c.category].append(rec.actual_duration_hours / 24.0)

    category_avg_days: list[dict[str, Any]] = []
    for cat, durs in category_durations.items():
        avg_d = round(sum(durs) / len(durs), 1) if durs else 0.0
        category_avg_days.append({"category": cat, "avg_disposal_days": avg_d, "sample_size": len(durs)})

    # 3. Status distribution
    all_recs = list(db.scalars(select(CaseSlaRecord)).all())
    status_counts = defaultdict(int)
    for r in all_recs:
        status_counts[r.status] += 1

    # 4. Escalations count by level
    esc_levels = defaultdict(int)
    escalations = list(db.scalars(select(SlaEscalation)).all())
    for e in escalations:
        esc_levels[f"Level {e.escalation_level}"] += 1

    return {
        "monthly_compliance_trend": monthly_trend,
        "category_avg_disposal_days": category_avg_days,
        "status_distribution": dict(status_counts),
        "escalation_distribution": dict(esc_levels),
        "total_records_tracked": len(all_recs),
    }


def export_records_csv(records: list[CaseSlaRecord]) -> StreamingResponse:
    """Generate safe, sanitized CSV export of SLA monitoring records."""
    output = io.StringIO(newline="")
    writer = csv.writer(output)

    headings = [
        "Case ID",
        "Institution",
        "Category",
        "Priority",
        "Current Bureau",
        "Assigned Officer",
        "Start Date",
        "Current Deadline",
        "Target Days",
        "Calendar Type",
        "SLA Status",
        "Consumed %",
        "Remaining Hours",
        "Elapsed Hours",
        "Is Paused",
        "Escalation Level",
    ]
    writer.writerow(headings)

    for r in records:
        case = r.case
        inst_name = case.institution.name if case and case.institution else "-"
        cat = case.category if case else "-"
        prio = case.priority.value if case and hasattr(case.priority, "value") else (str(case.priority) if case else "-")
        bureau = case.current_bureau.code if case and case.current_bureau else "-"
        officer = case.assigned_officer.full_name if case and case.assigned_officer else "Unassigned"
        start_str = r.start_time.strftime("%d-%m-%Y") if r.start_time else "-"
        deadline_str = r.current_deadline.strftime("%d-%m-%Y") if r.current_deadline else "-"

        # Prevent CSV injection for values starting with =, +, -, @
        def safe(val: Any) -> str:
            s = str(val if val is not None else "-")
            if s and s[0] in ("=", "+", "-", "@"):
                return f"'{s}"
            return s

        writer.writerow([
            safe(r.case_ref),
            safe(inst_name),
            safe(cat),
            safe(prio),
            safe(bureau),
            safe(officer),
            safe(start_str),
            safe(deadline_str),
            safe(r.target_duration_days),
            safe(r.calendar_type),
            safe(r.status),
            safe(f"{r.consumed_percentage}%"),
            safe(r.remaining_duration_hours),
            safe(r.elapsed_duration_hours),
            safe("Yes" if r.is_paused else "No"),
            safe(r.escalation_level),
        ])

    filename = f"sla_monitoring_report_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

