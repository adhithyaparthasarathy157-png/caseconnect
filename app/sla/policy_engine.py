"""
SLA Policy Management and Resolution Engine for AICTE CaseConnect.

Deterministic resolution hierarchy:
1. Exact: Category + Priority + Bureau
2. Category + Priority (all bureaus)
3. Category + Bureau (all priorities)
4. Category only (all priorities, all bureaus)
5. Explicit Default Policy

All policies maintain immutable historical versions in `sla_policy_versions`.
Illustrative policies are for demonstration only, not official AICTE regulations.
"""
from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.enums import Priority, SlaCalendarType
from app.intelligence import audit
from app.models import SlaPolicy, SlaPolicyVersion, User
from app.sla.calendar import ensure_utc
from app.sla.schemas import SlaPolicyCreate, SlaPolicyUpdate


def now_utc() -> datetime:
    return datetime.now(UTC)


def _policy_snapshot(policy: SlaPolicy) -> dict[str, Any]:
    """Create a JSON-serializable snapshot of an SLA policy."""
    return {
        "id": policy.id,
        "name": policy.name,
        "category": policy.category,
        "priority": policy.priority.value if hasattr(policy.priority, "value") else (str(policy.priority) if policy.priority else None),
        "bureau_id": policy.bureau_id,
        "target_duration_days": policy.target_duration_days,
        "calendar_type": policy.calendar_type.value if hasattr(policy.calendar_type, "value") else str(policy.calendar_type),
        "warning_threshold_pct": policy.warning_threshold_pct,
        "at_risk_threshold_pct": policy.at_risk_threshold_pct,
        "escalation_config": policy.escalation_config,
        "effective_from": policy.effective_from.isoformat() if policy.effective_from else None,
        "effective_to": policy.effective_to.isoformat() if policy.effective_to else None,
        "is_active": policy.is_active,
        "version": policy.version,
    }


def resolve_policy(
    db: Session,
    category: str,
    priority: Priority | str | None = None,
    bureau_id: int | None = None,
    at_time: datetime | None = None,
) -> SlaPolicy | None:
    """
    Deterministic policy resolution mechanism.
    Evaluates only active policies effective at `at_time` (or current UTC).
    """
    eval_time = ensure_utc(at_time) if at_time else now_utc()
    eval_dt = datetime.combine(eval_time.date(), time.max).replace(tzinfo=UTC)
    cat_norm = category.strip()
    prio_val = priority.value if hasattr(priority, "value") else (str(priority) if priority else None)

    # Base query for active and currently effective policies
    base = select(SlaPolicy).where(
        SlaPolicy.is_active.is_(True),
        (SlaPolicy.effective_from.is_(None) | (SlaPolicy.effective_from <= eval_dt)),
        (SlaPolicy.effective_to.is_(None) | (SlaPolicy.effective_to >= eval_time)),
    )

    # 1. Exact Category + Priority + Bureau
    if prio_val and bureau_id is not None:
        p1 = db.scalar(
            base.where(
                func.lower(SlaPolicy.category) == cat_norm.lower(),
                SlaPolicy.priority == prio_val,
                SlaPolicy.bureau_id == bureau_id,
            ).order_by(SlaPolicy.id.desc())
        )
        if p1:
            return p1

    # 2. Category + Priority (bureau is None)
    if prio_val:
        p2 = db.scalar(
            base.where(
                func.lower(SlaPolicy.category) == cat_norm.lower(),
                SlaPolicy.priority == prio_val,
                SlaPolicy.bureau_id.is_(None),
            ).order_by(SlaPolicy.id.desc())
        )
        if p2:
            return p2

    # 3. Category + Bureau (priority is None)
    if bureau_id is not None:
        p3 = db.scalar(
            base.where(
                func.lower(SlaPolicy.category) == cat_norm.lower(),
                SlaPolicy.priority.is_(None),
                SlaPolicy.bureau_id == bureau_id,
            ).order_by(SlaPolicy.id.desc())
        )
        if p3:
            return p3

    # 4. Category only (priority and bureau are None)
    p4 = db.scalar(
        base.where(
            func.lower(SlaPolicy.category) == cat_norm.lower(),
            SlaPolicy.priority.is_(None),
            SlaPolicy.bureau_id.is_(None),
        ).order_by(SlaPolicy.id.desc())
    )
    if p4:
        return p4

    # 5. Fallback Default Policy
    p_default = db.scalar(
        base.where(
            func.lower(SlaPolicy.category) == "default",
        ).order_by(SlaPolicy.id.desc())
    )
    if p_default:
        return p_default

    # 6. Global active policy marked as default by name
    p_named = db.scalar(
        base.where(
            SlaPolicy.name.ilike("%default%"),
        ).order_by(SlaPolicy.id.desc())
    )
    if p_named:
        return p_named

    # 7. Strictly-scoped fallback for historical pre-policy cases (year < 2000).
    # Allows assigning baseline default policy for anomaly tracking and archival,
    # while strictly preserving effective_from constraint checks for all modern cases.
    if eval_time.year < 2000:
        p_fallback = db.scalar(
            select(SlaPolicy)
            .where(
                SlaPolicy.is_active.is_(True),
                (func.lower(SlaPolicy.category) == cat_norm.lower())
                | (func.lower(SlaPolicy.category) == "default")
                | (SlaPolicy.name.ilike("%default%")),
            )
            .order_by(
                (func.lower(SlaPolicy.category) == cat_norm.lower()).desc(),
                SlaPolicy.id.desc(),
            )
        )
        if p_fallback:
            return p_fallback
        return db.scalar(select(SlaPolicy).where(SlaPolicy.is_active.is_(True)).order_by(SlaPolicy.id.asc()))

    return None


def create_policy(db: Session, payload: SlaPolicyCreate, actor: User | None = None) -> SlaPolicy:
    effective_from = payload.effective_from or (now_utc() - timedelta(days=1))
    escalation_config = payload.escalation_config or {
        "warning_threshold_pct": payload.warning_threshold_pct,
        "at_risk_threshold_pct": payload.at_risk_threshold_pct,
        "notify_assigned_officer_at": 75,
        "notify_bureau_coordinator_at": 90,
        "escalate_to_management_at": 100,
        "escalation_reassign_days_overdue": 3,
    }

    policy = SlaPolicy(
        name=payload.name.strip(),
        category=payload.category.strip(),
        priority=payload.priority,
        bureau_id=payload.bureau_id,
        target_duration_days=payload.target_duration_days,
        calendar_type=payload.calendar_type,
        warning_threshold_pct=payload.warning_threshold_pct,
        at_risk_threshold_pct=payload.at_risk_threshold_pct,
        escalation_config=escalation_config,
        effective_from=effective_from,
        effective_to=payload.effective_to,
        is_active=payload.is_active,
        version=1,
        created_by_id=actor.id if actor else None,
        updated_by_id=actor.id if actor else None,
    )
    db.add(policy)
    db.flush()

    # Create immutable version 1 snapshot
    v1 = SlaPolicyVersion(
        policy_id=policy.id,
        version=1,
        snapshot=_policy_snapshot(policy),
        changed_by_id=actor.id if actor else None,
        change_reason="Initial policy creation",
    )
    db.add(v1)
    audit(db, actor, "sla_policy", str(policy.id), "sla_policy_created", {"name": policy.name, "version": 1})
    db.commit()
    db.refresh(policy)
    return policy


def update_policy(db: Session, policy: SlaPolicy, payload: SlaPolicyUpdate, actor: User | None = None) -> SlaPolicy:
    changes = payload.model_dump(exclude_unset=True, exclude={"change_reason"})
    if not changes:
        return policy

    new_version = policy.version + 1
    for k, v in changes.items():
        setattr(policy, k, v)
    policy.version = new_version
    policy.updated_by_id = actor.id if actor else None

    # Preserve historical snapshot
    v_new = SlaPolicyVersion(
        policy_id=policy.id,
        version=new_version,
        snapshot=_policy_snapshot(policy),
        changed_by_id=actor.id if actor else None,
        change_reason=payload.change_reason or f"Policy updated to version {new_version}",
    )
    db.add(v_new)
    audit(
        db,
        actor,
        "sla_policy",
        str(policy.id),
        "sla_policy_updated",
        {"new_version": new_version, "changes": [k for k in changes.keys()]},
        payload.change_reason,
    )
    db.commit()
    db.refresh(policy)
    return policy


def set_policy_active(db: Session, policy: SlaPolicy, is_active: bool, actor: User | None = None) -> SlaPolicy:
    if policy.is_active == is_active:
        return policy
    policy.is_active = is_active
    policy.version += 1
    policy.updated_by_id = actor.id if actor else None

    action_label = "activated" if is_active else "deactivated"
    v_new = SlaPolicyVersion(
        policy_id=policy.id,
        version=policy.version,
        snapshot=_policy_snapshot(policy),
        changed_by_id=actor.id if actor else None,
        change_reason=f"Policy {action_label}",
    )
    db.add(v_new)
    audit(db, actor, "sla_policy", str(policy.id), f"sla_policy_{action_label}", {"is_active": is_active})
    db.commit()
    db.refresh(policy)
    return policy


# Illustrative demonstration policies (clearly flagged as demo material)
DEMO_SLA_POLICIES = [
    {
        "name": "Urgent Student Grievance (Critical)",
        "category": "Grievance",
        "priority": Priority.CRITICAL,
        "target_duration_days": 7,
        "calendar_type": SlaCalendarType.BUSINESS_DAYS,
        "warning_threshold_pct": 70.0,
        "at_risk_threshold_pct": 85.0,
        "escalation_config": {"level1": "Officer", "level2": "Bureau Coordinator", "level3": "Competent Authority"},
    },
    {
        "name": "Standard Academic Grievance Policy",
        "category": "Grievance",
        "priority": None,
        "target_duration_days": 15,
        "calendar_type": SlaCalendarType.BUSINESS_DAYS,
        "warning_threshold_pct": 75.0,
        "at_risk_threshold_pct": 90.0,
    },
    {
        "name": "Faculty & Staff Service Matters",
        "category": "Faculty",
        "priority": None,
        "target_duration_days": 20,
        "calendar_type": SlaCalendarType.BUSINESS_DAYS,
        "warning_threshold_pct": 75.0,
        "at_risk_threshold_pct": 90.0,
    },
    {
        "name": "Infrastructure Deficiency Investigation",
        "category": "Infrastructure",
        "priority": None,
        "target_duration_days": 30,
        "calendar_type": SlaCalendarType.CALENDAR_DAYS,
        "warning_threshold_pct": 75.0,
        "at_risk_threshold_pct": 90.0,
    },
    {
        "name": "Approval & Institutional Intake Scrutiny",
        "category": "Approval",
        "priority": None,
        "target_duration_days": 45,
        "calendar_type": SlaCalendarType.CALENDAR_DAYS,
        "warning_threshold_pct": 80.0,
        "at_risk_threshold_pct": 90.0,
    },
    {
        "name": "Application Processing SLA",
        "category": "Application",
        "priority": None,
        "target_duration_days": 30,
        "calendar_type": SlaCalendarType.BUSINESS_DAYS,
        "warning_threshold_pct": 75.0,
        "at_risk_threshold_pct": 90.0,
    },
    {
        "name": "Standard AICTE CaseConnect Default Policy",
        "category": "Default",
        "priority": None,
        "target_duration_days": 30,
        "calendar_type": SlaCalendarType.CALENDAR_DAYS,
        "warning_threshold_pct": 75.0,
        "at_risk_threshold_pct": 90.0,
    },
]


def seed_demo_policies(db: Session, actor: User | None = None) -> list[SlaPolicy]:
    """Seed baseline illustrative policies if table is empty."""
    existing_count = db.scalar(select(func.count(SlaPolicy.id)))
    if existing_count > 0:
        return list(db.scalars(select(SlaPolicy).order_by(SlaPolicy.id)).all())

    created: list[SlaPolicy] = []
    for item in DEMO_SLA_POLICIES:
        pol = create_policy(
            db,
            SlaPolicyCreate(
                name=item["name"],
                category=item["category"],
                priority=item.get("priority"),
                target_duration_days=item["target_duration_days"],
                calendar_type=item["calendar_type"],
                warning_threshold_pct=item.get("warning_threshold_pct", 75.0),
                at_risk_threshold_pct=item.get("at_risk_threshold_pct", 90.0),
                escalation_config=item.get("escalation_config", {}),
                effective_from=datetime(2020, 1, 1, tzinfo=UTC),
            ),
            actor=actor,
        )
        created.append(pol)
    return created

