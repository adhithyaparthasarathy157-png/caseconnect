"""
Calendar and Deadline Calculation Utilities for AICTE CaseConnect SLA Engine.

Supports both calendar days and business days calculation with Indian official
holidays and configurable working days.
All timestamps are timezone-aware (UTC).

Holiday Policy
--------------
CENTRAL_GAZETTED_HOLIDAYS
    Mandatory national holidays applicable to all AICTE bureaus regardless of
    location. Includes the three gazette-notified national holidays (Republic
    Day, Independence Day, Gandhi Jayanti) plus New Year's Day and Christmas
    which are observed across central government offices.

STATE_OBSERVANCE_HOLIDAYS
    State-specific or regionally observed festivals included here for
    *illustrative* purposes only. These vary by bureau location and should NOT
    be applied universally. Bureau-level SLA policies may opt-in to specific
    dates by adding them to the policy's ``custom_holidays`` JSON field.

DEFAULT_HOLIDAYS_YEARS
    Union of the above sets — kept for backward compatibility.  New code should
    prefer passing an explicit ``holiday_set`` built from
    ``get_applicable_holidays()``.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Iterable

from app.enums import SlaCalendarType

# ---------------------------------------------------------------------------
# Central / National holidays — universally applicable to all AICTE bureaus
# ---------------------------------------------------------------------------
CENTRAL_GAZETTED_HOLIDAYS: set[date] = {
    # 2025
    date(2025, 1, 1),   # New Year's Day
    date(2025, 1, 26),  # Republic Day (National Holiday)
    date(2025, 8, 15),  # Independence Day (National Holiday)
    date(2025, 10, 2),  # Gandhi Jayanti (National Holiday)
    date(2025, 12, 25), # Christmas Day
    # 2026
    date(2026, 1, 1),   # New Year's Day
    date(2026, 1, 26),  # Republic Day (National Holiday)
    date(2026, 8, 15),  # Independence Day (National Holiday)
    date(2026, 10, 2),  # Gandhi Jayanti (National Holiday)
    date(2026, 12, 25), # Christmas Day
    # 2027
    date(2027, 1, 1),
    date(2027, 1, 26),
    date(2027, 8, 15),
    date(2027, 10, 2),
    date(2027, 12, 25),
}

# ---------------------------------------------------------------------------
# State-specific / regional observances — ILLUSTRATIVE ONLY
# Not universally applicable. Bureaus located in states that observe these
# festivals may opt-in by including them in their policy custom_holidays list.
# ---------------------------------------------------------------------------
STATE_OBSERVANCE_HOLIDAYS: set[date] = {
    # 2025
    date(2025, 10, 20),  # Diwali 2025 (illustrative — state-specific)
    # 2026
    date(2026, 3, 4),    # Holi 2026 (illustrative — state-specific)
    date(2026, 11, 8),   # Diwali 2026 (illustrative — state-specific)
}

# ---------------------------------------------------------------------------
# Backward-compatible union — used by default when no holiday_set provided
# ---------------------------------------------------------------------------
DEFAULT_HOLIDAYS_YEARS: set[date] = CENTRAL_GAZETTED_HOLIDAYS | STATE_OBSERVANCE_HOLIDAYS


def get_applicable_holidays(
    include_state_observances: bool = False,
    custom_holiday_dates: Iterable[date] | None = None,
) -> set[date]:
    """
    Build the set of holidays applicable for a given context.

    Parameters
    ----------
    include_state_observances:
        Include the illustrative state-specific festival dates. Should be
        True only when the bureau is located in a state that officially
        observes these festivals.
    custom_holiday_dates:
        Additional bureau- or policy-specific holiday dates (e.g. local
        public holidays, state-declared holidays). Typically sourced from
        ``SlaPolicy.custom_holidays``.

    Returns
    -------
    set[date]
        The resolved holiday set to pass to ``is_working_day()`` or
        ``calculate_deadline()``.
    """
    holidays = set(CENTRAL_GAZETTED_HOLIDAYS)
    if include_state_observances:
        holidays |= STATE_OBSERVANCE_HOLIDAYS
    if custom_holiday_dates:
        holidays.update(custom_holiday_dates)
    return holidays


def ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime has UTC timezone."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def is_working_day(d: date, holidays: set[date] | None = None) -> bool:
    """Working days are Monday (0) to Friday (4), excluding holidays."""
    if d.weekday() >= 5:  # Saturday or Sunday
        return False
    active_holidays = holidays if holidays is not None else DEFAULT_HOLIDAYS_YEARS
    return d not in active_holidays


def add_business_days(start_dt: datetime, days: int, holidays: set[date] | None = None) -> datetime:
    """
    Add business days skipping weekends and holidays.
    Preserves the time portion of start_dt.
    """
    cur_date = start_dt.date()
    added = 0
    while added < days:
        cur_date += timedelta(days=1)
        if is_working_day(cur_date, holidays):
            added += 1
    return datetime.combine(cur_date, start_dt.time(), tzinfo=start_dt.tzinfo or UTC)


def add_calendar_days(start_dt: datetime, days: int) -> datetime:
    """Add calendar days directly."""
    return start_dt + timedelta(days=days)


def calculate_deadline(
    start_dt: datetime,
    duration_days: int,
    calendar_type: str | SlaCalendarType = SlaCalendarType.CALENDAR_DAYS,
    holidays: set[date] | None = None,
) -> datetime:
    """Deterministic deadline calculation according to policy calendar type."""
    start_utc = ensure_utc(start_dt)
    cal_type_str = calendar_type.value if hasattr(calendar_type, "value") else str(calendar_type)
    if cal_type_str == SlaCalendarType.BUSINESS_DAYS.value or cal_type_str == "business_days":
        return add_business_days(start_utc, duration_days, holidays)
    return add_calendar_days(start_utc, duration_days)


def calculate_metrics(
    start_time: datetime,
    current_deadline: datetime,
    target_duration_days: int,
    calendar_type: str | SlaCalendarType,
    accumulated_paused_seconds: int = 0,
    is_paused: bool = False,
    now_time: datetime | None = None,
) -> tuple[float, float, float]:
    """
    Calculate elapsed hours, remaining hours, and consumed percentage.

    Returns:
        (elapsed_hours, remaining_hours, consumed_percentage)
    """
    start_utc = ensure_utc(start_time)
    deadline_utc = ensure_utc(current_deadline)
    current_now = ensure_utc(now_time or datetime.now(UTC))

    # Total nominal duration between start and deadline in seconds
    nominal_total_seconds = max((deadline_utc - start_utc).total_seconds(), 3600.0)

    # Actual elapsed wall clock seconds minus accumulated paused duration
    gross_elapsed_seconds = max(0.0, (current_now - start_utc).total_seconds())
    effective_elapsed_seconds = max(0.0, gross_elapsed_seconds - accumulated_paused_seconds)

    # Elapsed hours and remaining hours
    elapsed_hours = round(effective_elapsed_seconds / 3600.0, 2)
    remaining_seconds = (deadline_utc - current_now).total_seconds()
    remaining_hours = round(remaining_seconds / 3600.0, 2)

    # Consumed percentage
    if nominal_total_seconds > 0:
        consumed_pct = round((effective_elapsed_seconds / nominal_total_seconds) * 100.0, 2)
    else:
        consumed_pct = 100.0

    return elapsed_hours, remaining_hours, consumed_pct

