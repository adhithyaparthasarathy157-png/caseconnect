"""Explainable local overlap scoring; suggestions never alter case outcomes."""
import re
from datetime import UTC, datetime
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import AlertSeverity, OverlapStatus
from app.models import Alert, AuditEvent, Case, OverlapCandidate, User


def normalise(value: str | None) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (value or "").casefold()))


def _score(left: Case, right: Case) -> tuple[int, bool, list[str]]:
    reasons: list[str] = []
    score = 0
    identity = left.institution_id == right.institution_id
    if identity:
        score += 35
        reasons.append("Same registered institution")
    else:
        return 0, False, reasons
    if left.category.casefold() == right.category.casefold():
        score += 15
        reasons.append("Same case category")
    description_similarity = SequenceMatcher(None, normalise(left.description), normalise(right.description)).ratio()
    subject_similarity = SequenceMatcher(None, normalise(left.subject), normalise(right.subject)).ratio()
    text_similarity = max(description_similarity, subject_similarity)
    if text_similarity >= 0.86:
        score += 40
        reasons.append(f"Near-duplicate complaint text ({round(text_similarity * 100)}%)")
    elif text_similarity >= 0.58:
        score += 20
        reasons.append(f"Related complaint text ({round(text_similarity * 100)}%)")
    if left.external_reference and normalise(left.external_reference) == normalise(right.external_reference):
        score += 25
        reasons.append("Matching external reference")
    if left.current_bureau_id != right.current_bureau_id:
        score += 5
        reasons.append("Involves different current bureaus")
    days = abs((left.receipt_date - right.receipt_date).days)
    if days <= 30:
        score += 5
        reasons.append("Received within 30 days")
    return min(score, 100), identity, reasons


def audit(db: Session, actor: User | None, entity_type: str, entity_id: str, action: str, details: dict | None = None, remarks: str | None = None) -> None:
    db.add(AuditEvent(entity_type=entity_type, entity_id=entity_id, action=action,
                      actor_id=actor.id if actor else None, details=details, remarks=remarks))


def create_alert(db: Session, *, key: str, alert_type: str, severity: AlertSeverity, title: str, message: str,
                 case: Case | None = None, overlap: OverlapCandidate | None = None) -> None:
    if db.scalar(select(Alert.id).where(Alert.dedupe_key == key)):
        return
    db.add(Alert(dedupe_key=key, alert_type=alert_type, severity=severity, title=title, message=message,
                 case_id=case.id if case else None, overlap_id=overlap.id if overlap else None,
                 bureau_id=case.current_bureau_id if case else None,
                 region=case.institution.region if case else None))


def refresh_overlaps(db: Session, case: Case | None = None) -> int:
    cases = [case] if case else list(db.scalars(select(Case)).all())
    created_or_updated = 0
    for current in cases:
        others = db.scalars(select(Case).where(Case.institution_id == current.institution_id, Case.id != current.id)).all()
        for other in others:
            low, high = sorted((current, other), key=lambda item: item.id)
            score, identity, reasons = _score(low, high)
            if score < 55:
                continue
            candidate = db.scalar(select(OverlapCandidate).where(OverlapCandidate.case_low_id == low.id, OverlapCandidate.case_high_id == high.id))
            if candidate:
                if candidate.status == OverlapStatus.PENDING:
                    candidate.similarity_score, candidate.identity_match, candidate.reasons = score, identity, reasons
                    created_or_updated += 1
                continue
            candidate = OverlapCandidate(case_low_id=low.id, case_high_id=high.id, similarity_score=score, identity_match=identity, reasons=reasons)
            db.add(candidate)
            db.flush()
            create_alert(db, key=f"overlap:{candidate.id}", alert_type="potential_overlap", severity=AlertSeverity.WARNING,
                         title="Potential overlapping cases", message="Potential Overlapping Cases - Coordination Required.", case=low, overlap=candidate)
            created_or_updated += 1
    return created_or_updated


def review_overlap(db: Session, candidate: OverlapCandidate, actor: User, status: OverlapStatus, remarks: str) -> OverlapCandidate:
    candidate.status, candidate.reviewer_id, candidate.reviewed_at, candidate.remarks = status, actor.id, datetime.now(UTC), remarks
    audit(db, actor, "overlap", str(candidate.id), "overlap_reviewed", {"status": status.value}, remarks)
    db.commit()
    db.refresh(candidate)
    return candidate
