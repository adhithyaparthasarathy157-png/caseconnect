import csv
import io
from collections import Counter
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import can_view_case, get_current_user
from app.enums import OverlapStatus
from app.intelligence import audit
from app.models import Case, Institution, OverlapCandidate, User

router = APIRouter(prefix="/api/analytics", tags=["analytics and reports"])


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def scoped_cases(db: Session, user: User, bureau_id: int | None = None, region: str | None = None, status: str | None = None, category: str | None = None, institution_id: int | None = None) -> list[Case]:
    query = select(Case).join(Institution).options(selectinload(Case.institution))
    if bureau_id: query = query.where(Case.current_bureau_id == bureau_id)
    if region: query = query.where(Institution.region == region)
    if status: query = query.where(Case.status == status)
    if category: query = query.where(Case.category == category)
    if institution_id: query = query.where(Case.institution_id == institution_id)
    return [case for case in db.scalars(query).all() if can_view_case(user, case)]


def count_by(cases: list[Case], key) -> dict[str, int]:
    return dict(sorted(Counter(str(key(case)) for case in cases).items()))


def csv_response(filename: str, headings: list[str], rows: list[list[object]]) -> StreamingResponse:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    def safe_cell(value: object) -> object:
        text = str(value)
        return f"'{text}" if text[:1] in {"=", "+", "-", "@"} else value
    writer.writerow(headings)
    writer.writerows([[safe_cell(value) for value in row] for row in rows])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={filename}"})


@router.get("/summary")
def summary(bureau_id: int | None = None, region: str | None = None, status: str | None = None, category: str | None = None, institution_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    cases = scoped_cases(db, user, bureau_id, region, status, category, institution_id)
    today = datetime.now(UTC)
    overdue = [case for case in cases if case.expected_disposal_date and as_utc(case.expected_disposal_date) < today and case.status.value not in {"Disposed", "Closed"}]
    statuses = count_by(cases, lambda case: case.status.value)
    ages = Counter("0-7 days" if (today - as_utc(case.receipt_at)).days <= 7 else "8-30 days" if (today - as_utc(case.receipt_at)).days <= 30 else "31-90 days" if (today - as_utc(case.receipt_at)).days <= 90 else "90+ days" for case in cases)
    disposed = sum(1 for case in cases if case.status.value in {"Disposed", "Closed"})
    candidates = db.scalars(select(OverlapCandidate).options(selectinload(OverlapCandidate.case_low).selectinload(Case.institution), selectinload(OverlapCandidate.case_high).selectinload(Case.institution))).all()
    overlap_count = sum(1 for item in candidates if item.status == OverlapStatus.PENDING and can_view_case(user, item.case_low) and can_view_case(user, item.case_high))
    monthly = count_by(cases, lambda case: as_utc(case.receipt_at).strftime("%Y-%m"))
    quarterly = count_by(cases, lambda case: f"{as_utc(case.receipt_at).year}-Q{(as_utc(case.receipt_at).month - 1) // 3 + 1}")
    outcomes = count_by([item for item in candidates if can_view_case(user, item.case_low) and can_view_case(user, item.case_high)], lambda item: item.status.value)
    return {"definitions": {"pending": "all statuses except Disposed and Closed", "overdue": "expected disposal date before now and not disposed/closed", "prototype": "No official AICTE SLA is implied."}, "total_received": len(cases), "pending": len(cases) - disposed, "under_process": statuses.get("Under Process", 0), "disposed": statuses.get("Disposed", 0) + statuses.get("Closed", 0), "transferred": statuses.get("Transferred", 0), "overdue": len(overdue), "disposal_rate": round(disposed / len(cases) * 100, 2) if cases else 0, "by_status": statuses, "by_bureau": count_by(cases, lambda case: case.current_bureau_id), "by_region": count_by(cases, lambda case: case.institution.region), "by_category": count_by(cases, lambda case: case.category), "ageing": dict(ages), "monthly_trend": monthly, "quarterly_trend": quarterly, "potential_overlaps": overlap_count, "overlap_outcomes": outcomes}


@router.get("/cases.csv")
def export_cases_csv(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> StreamingResponse:
    cases = scoped_cases(db, user)
    audit(db, user, "report", "cases", "export_csv", {"rows": len(cases)})
    db.commit()
    return csv_response("caseconnect-cases.csv", ["Case ID", "Institution", "Region", "Status", "Category", "Current Bureau", "Expected Disposal"], [[case.case_id, case.institution.name, case.institution.region, case.status.value, case.category, case.current_bureau_id, case.expected_disposal_date.isoformat() if case.expected_disposal_date else ""] for case in cases])


@router.get("/bureau-summary.csv")
def export_bureau_summary_csv(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> StreamingResponse:
    cases = scoped_cases(db, user)
    counts = count_by(cases, lambda case: case.current_bureau_id)
    audit(db, user, "report", "bureau_summary", "export_csv", {"rows": len(counts)})
    db.commit()
    return csv_response("caseconnect-bureau-summary.csv", ["Bureau ID", "Cases"], [[bureau, total] for bureau, total in counts.items()])


@router.get("/region-summary.csv")
def export_region_summary_csv(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> StreamingResponse:
    cases = scoped_cases(db, user)
    counts = count_by(cases, lambda case: case.institution.region)
    audit(db, user, "report", "region_summary", "export_csv", {"rows": len(counts)})
    db.commit()
    return csv_response("caseconnect-region-summary.csv", ["Region", "Cases"], [[region, total] for region, total in counts.items()])


@router.get("/overlaps.csv")
def export_overlaps_csv(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> StreamingResponse:
    candidates = db.scalars(select(OverlapCandidate).options(selectinload(OverlapCandidate.case_low).selectinload(Case.institution), selectinload(OverlapCandidate.case_high).selectinload(Case.institution))).all()
    visible = [item for item in candidates if can_view_case(user, item.case_low) and can_view_case(user, item.case_high)]
    audit(db, user, "report", "overlaps", "export_csv", {"rows": len(visible)})
    db.commit()
    return csv_response("caseconnect-overlaps.csv", ["Overlap ID", "Case A", "Case B", "Institution", "Score", "Status", "Reasons"], [[item.id, item.case_low.case_id, item.case_high.case_id, item.case_low.institution.name, item.similarity_score, item.status.value, "; ".join(item.reasons)] for item in visible])


@router.get("/ageing.csv")
def export_ageing_csv(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> StreamingResponse:
    cases = scoped_cases(db, user)
    today = datetime.now(UTC)
    rows = [[case.case_id, case.institution.name, (today - as_utc(case.receipt_at)).days, case.status.value] for case in cases]
    audit(db, user, "report", "ageing", "export_csv", {"rows": len(rows)})
    db.commit()
    return csv_response("caseconnect-ageing.csv", ["Case ID", "Institution", "Age days", "Status"], rows)


@router.get("/institutions/{institution_id}/history.csv")
def export_institution_history_csv(institution_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> StreamingResponse:
    cases = scoped_cases(db, user, institution_id=institution_id)
    audit(db, user, "report", f"institution:{institution_id}", "export_csv", {"rows": len(cases)})
    db.commit()
    return csv_response("caseconnect-institution-history.csv", ["Case ID", "Subject", "Status", "Current Bureau", "Last Action"], [[case.case_id, case.subject, case.status.value, case.current_bureau_id, case.last_action] for case in cases])
