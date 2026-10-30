"""
Complaint-level AI Screening Decision Engine.
Screens complaint submissions BEFORE they become registered cases.
Outcomes: PASSED, REJECTED_AT_INTAKE, CORRECTION_REQUIRED, NEEDS_HUMAN_REVIEW

Uses rule-based validation + sentence-transformers for duplicate detection.
Explicitly labeled as rule-based — not a trained predictive model.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Case, Institution

# Lazy-load the embedding model (same as document_intelligence uses)
_EMBED_MODEL: SentenceTransformer | None = None


def _get_embed_model() -> SentenceTransformer:
    global _EMBED_MODEL
    if _EMBED_MODEL is None:
        _EMBED_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return _EMBED_MODEL


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    return float(dot / norm) if norm > 0 else 0.0


# ------------------------------------------------------------------
# Screening criterion checks
# ------------------------------------------------------------------

def _check_permanent_id(submission: dict) -> dict | None:
    pid = (submission.get("permanent_id") or "").strip()
    if not pid:
        return {
            "criterion_id": "mandatory_permanent_id",
            "failure_category": "MISSING_MANDATORY_FIELD",
            "extracted_evidence": "permanent_id field is empty or absent",
            "expected": "Non-empty institution Permanent ID (e.g. 1-XXXXXXX)",
            "actual": repr(pid),
            "explanation": "Every complaint must identify the institution by its AICTE Permanent ID. Without this, the complaint cannot be routed to the correct bureau or linked to institution records.",
            "suggested_correction": "Provide the institution's valid Permanent ID as assigned by AICTE (found on the institution's approval letter).",
        }
    return None


def _check_subject(submission: dict) -> dict | None:
    subject = (submission.get("subject") or "").strip()
    if len(subject) < 10:
        return {
            "criterion_id": "subject_min_length",
            "failure_category": "INSUFFICIENT_CONTENT",
            "extracted_evidence": f"Subject: '{subject}' ({len(subject)} chars)",
            "expected": "Subject of at least 10 characters describing the complaint",
            "actual": f"{len(subject)} characters",
            "explanation": "A complaint subject must be specific enough to identify the nature of the issue and allow routing.",
            "suggested_correction": "Provide a clear, specific subject (e.g. 'Delay in refund of caution money by ABCD Engineering College').",
        }
    return None


def _check_description_sufficiency(submission: dict) -> dict | None:
    description = (submission.get("description") or "").strip()
    word_count = len(description.split())
    if word_count < 20:
        return {
            "criterion_id": "description_min_words",
            "failure_category": "INSUFFICIENT_CONTENT",
            "extracted_evidence": f"Description word count: {word_count}",
            "expected": "At least 20 words describing the complaint with specific details",
            "actual": f"{word_count} words",
            "explanation": "Complaint descriptions must provide sufficient factual detail for an officer to assess the issue without contacting the institution for basic information.",
            "suggested_correction": "Expand the description to include: what happened, when it happened, what was promised, and how it violates AICTE norms.",
        }
    return None


def _check_category(submission: dict) -> dict | None:
    valid_categories = {"Academic", "Financial", "Infrastructure", "Faculty", "Accreditation", "Affiliation", "Admission", "Conduct", "Examination", "Other"}
    category = (submission.get("category") or "").strip()
    if not category:
        return {
            "criterion_id": "mandatory_category",
            "failure_category": "MISSING_MANDATORY_FIELD",
            "extracted_evidence": "category field is empty or absent",
            "expected": f"One of: {', '.join(sorted(valid_categories))}",
            "actual": repr(category),
            "explanation": "Complaint category is required for routing to the correct bureau and officer.",
            "suggested_correction": "Select the most appropriate complaint category from the available options.",
        }
    if category not in valid_categories:
        return {
            "criterion_id": "valid_category_value",
            "failure_category": "INVALID_FIELD_VALUE",
            "extracted_evidence": f"category = '{category}'",
            "expected": f"One of: {', '.join(sorted(valid_categories))}",
            "actual": category,
            "explanation": "Unrecognised complaint category cannot be processed.",
            "suggested_correction": f"Use one of the recognised categories: {', '.join(sorted(valid_categories))}",
        }
    return None


def _check_dates(submission: dict) -> dict | None:
    incident_date_raw = submission.get("incident_date")
    if not incident_date_raw:
        return None  # Optional field — do not reject for missing incident date
    try:
        if isinstance(incident_date_raw, str):
            incident_date = datetime.fromisoformat(incident_date_raw.replace("Z", "+00:00")).date()
        else:
            incident_date = incident_date_raw
        today = datetime.now(UTC).date()
        if incident_date > today:
            return {
                "criterion_id": "incident_date_not_future",
                "failure_category": "CONTRADICTORY_INFORMATION",
                "extracted_evidence": f"incident_date = {incident_date}, submission_date = {today}",
                "expected": "Incident date must be today or in the past",
                "actual": f"Incident date {incident_date} is {(incident_date - today).days} days in the future",
                "explanation": "A complaint cannot describe an incident that has not yet occurred.",
                "suggested_correction": "Correct the incident date to reflect when the issue actually occurred.",
            }
    except (ValueError, TypeError):
        return {
            "criterion_id": "incident_date_valid_format",
            "failure_category": "INVALID_FIELD_VALUE",
            "extracted_evidence": f"incident_date = {incident_date_raw!r}",
            "expected": "ISO 8601 date string (YYYY-MM-DD)",
            "actual": repr(incident_date_raw),
            "explanation": "Incident date could not be parsed.",
            "suggested_correction": "Provide the incident date in YYYY-MM-DD format.",
        }
    return None


def _check_institution_exists(submission: dict, db: Session) -> tuple[dict | None, Institution | None]:
    pid = (submission.get("permanent_id") or "").strip()
    if not pid:
        return None, None
    institution = db.scalar(select(Institution).where(Institution.permanent_id == pid))
    if institution is None:
        return {
            "criterion_id": "institution_exists_in_registry",
            "failure_category": "UNRESOLVABLE_REFERENCE",
            "extracted_evidence": f"permanent_id = '{pid}' not found in institution registry",
            "expected": "Permanent ID must match a registered institution in AICTE records",
            "actual": f"No institution found with permanent_id = '{pid}'",
            "explanation": "The institution could not be identified in the registry. Complaints can only be filed against registered institutions.",
            "suggested_correction": "Verify the Permanent ID and ensure it matches the institution's AICTE registration.",
        }, None
    return None, institution


def _check_duplicate(submission: dict, institution: Institution | None, db: Session) -> dict | None:
    """Semantic duplicate detection using sentence-transformers + exact-match fallback."""
    if institution is None:
        return None
    description = (submission.get("description") or "").strip()
    subject = (submission.get("subject") or "").strip()
    if not description and not subject:
        return None

    existing_cases = db.scalars(
        select(Case).where(Case.institution_id == institution.id)
    ).all()

    if not existing_cases:
        return None

    try:
        model = _get_embed_model()
        query_text = f"{subject} {description}"
        query_vec = model.encode([query_text])[0]

        best_score = 0.0
        best_case_id = None
        for case in existing_cases:
            case_text = f"{case.subject} {case.description}"
            case_vec = model.encode([case_text])[0]
            sim = _cosine_sim(query_vec, case_vec)
            if sim > best_score:
                best_score = sim
                best_case_id = case.case_id
    except Exception:
        # Fallback: exact subject match
        for case in existing_cases:
            if (case.subject or "").strip().lower() == subject.lower():
                return {
                    "criterion_id": "no_exact_duplicate_subject",
                    "failure_category": "POTENTIAL_DUPLICATE",
                    "extracted_evidence": f"Subject exactly matches existing case {case.case_id}",
                    "expected": "No existing open case with identical subject for the same institution",
                    "actual": f"Identical subject found in case {case.case_id}",
                    "explanation": "This complaint appears to duplicate an existing case. Duplicate submissions waste administrative resources.",
                    "suggested_correction": f"Review existing case {case.case_id} to check if it already covers your complaint. If not, describe how your complaint differs.",
                }
        return None

    # Semantic duplicate threshold: 0.92 = near-duplicate, 0.80 = possible overlap
    if best_score >= 0.92:
        return {
            "criterion_id": "no_semantic_duplicate",
            "failure_category": "POTENTIAL_DUPLICATE",
            "extracted_evidence": f"Semantic similarity {round(best_score * 100)}% with case {best_case_id} for same institution",
            "expected": "Complaint text should be substantially different from existing open cases",
            "actual": f"Complaint text is {round(best_score * 100)}% semantically similar to case {best_case_id}",
            "explanation": (
                f"This complaint is nearly identical (semantic similarity: {round(best_score * 100)}%) "
                f"to existing case {best_case_id}. Possible duplicate submission detected by AI semantic matching. "
                "Note: This is a similarity score, not a confirmed duplicate — human review required."
            ),
            "suggested_correction": f"Check existing case {best_case_id}. If your complaint is different, explain how it differs in your description.",
        }
    elif best_score >= 0.80:
        # High similarity but not certain — flag for human review rather than rejection
        return {
            "criterion_id": "possible_overlap_check",
            "failure_category": "POSSIBLE_OVERLAP",
            "extracted_evidence": f"Semantic similarity {round(best_score * 100)}% with case {best_case_id}",
            "expected": "Complaint text should clearly distinguish from existing complaints if overlapping",
            "actual": f"Possible overlap ({round(best_score * 100)}% similar) with case {best_case_id}",
            "explanation": (
                f"This complaint is possibly related to existing case {best_case_id} "
                f"(semantic similarity: {round(best_score * 100)}%). This is flagged for human review, not automatic rejection."
            ),
            "suggested_correction": "If this is a new complaint, clarify in your description how it differs from any previous complaints about this institution.",
            "_severity": "NEEDS_HUMAN_REVIEW",  # Special marker — not an outright rejection
        }
    return None


# ------------------------------------------------------------------
# Main screening function
# ------------------------------------------------------------------

def screen_complaint_submission(
    submission: dict,
    db: Session,
    uploaded_files: list[tuple[bytes, str, str | None]] | None = None,
) -> dict[str, Any]:
    """
    Screen a complaint submission through all criteria, including uploaded documents.
    Returns screening result with outcome, failures, and explanations.
    
    Outcomes:
    - PASSED: All mandatory checks passed; ready for case registration
    - REJECTED_AT_INTAKE: Clear mandatory failure(s); cannot proceed
    - CORRECTION_REQUIRED: Correctable issues found
    - NEEDS_HUMAN_REVIEW: Ambiguous or possible-overlap — human decision required
    """
    failures: list[dict] = []
    human_review_triggers: list[dict] = []
    document_screening_results: dict[str, Any] | None = None

    # Field-level checks
    for check_fn in [_check_permanent_id, _check_subject, _check_description_sufficiency, _check_category, _check_dates]:
        result = check_fn(submission)
        if result:
            failures.append(result)

    # Registry check
    registry_failure, institution = _check_institution_exists(submission, db)
    if registry_failure:
        failures.append(registry_failure)

    # Document Screening Check (if files provided or explicitly evaluated)
    from app.ai.document_screening import screen_uploaded_documents_for_complaint
    files_to_check: list[tuple[bytes, str, str | None]] = []
    has_file_input = False

    if uploaded_files is not None:
        has_file_input = True
        files_to_check.extend(uploaded_files)

    if submission.get("uploaded_files") is not None:
        has_file_input = True
        files_to_check.extend(submission["uploaded_files"])

    if "document_attachments" in submission:
        has_file_input = True
        for att in (submission.get("document_attachments") or []):
            content = att.get("content", "")
            filename = att.get("filename", "evidence.txt")
            content_type = att.get("content_type", "text/plain")
            files_to_check.append((content.encode("utf-8") if isinstance(content, str) else content, filename, content_type))

    # Run document screening only when file screening is active
    if has_file_input:
        doc_res = screen_uploaded_documents_for_complaint(
            files=files_to_check,
            complaint_data={**submission, "institution_id": institution.id if institution else None},
            db=db,
        )
        document_screening_results = doc_res
        if doc_res.get("document_failures"):
            failures.extend(doc_res["document_failures"])
        if doc_res.get("document_human_reviews"):
            human_review_triggers.extend(doc_res["document_human_reviews"])

    # Duplicate check (only if institution found)
    if institution:
        dup_result = _check_duplicate(submission, institution, db)
        if dup_result:
            severity = dup_result.pop("_severity", None)
            if severity == "NEEDS_HUMAN_REVIEW":
                human_review_triggers.append(dup_result)
            else:
                failures.append(dup_result)

    # Determine outcome
    hard_failure_categories = {
        "MISSING_MANDATORY_FIELD",
        "UNRESOLVABLE_REFERENCE",
        "INVALID_FIELD_VALUE",
        "CONTRADICTORY_INFORMATION",
        "UNREADABLE_OR_CORRUPTED_DOCUMENT",
        "IRRELEVANT_DOCUMENT",
        "INSTITUTION_ID_MISMATCH",
        "MISSING_MANDATORY_EVIDENCE",
    }
    correctable_categories = {"INSUFFICIENT_CONTENT", "POTENTIAL_DUPLICATE", "CROSS_DOCUMENT_CONTRADICTION"}

    hard_failures = [f for f in failures if f.get("failure_category") in hard_failure_categories]
    correctable_failures = [f for f in failures if f.get("failure_category") in correctable_categories]

    if hard_failures:
        outcome = "REJECTED_AT_INTAKE"
        outcome_explanation = (
            f"{len(hard_failures)} mandatory criterion/criteria failed. "
            "Submission cannot proceed until these are resolved by the institution."
        )
    elif correctable_failures and not human_review_triggers:
        outcome = "CORRECTION_REQUIRED"
        outcome_explanation = (
            f"{len(correctable_failures)} correctable issue(s) found. "
            "Institution must address these before the complaint can be registered."
        )
    elif human_review_triggers or (correctable_failures and human_review_triggers):
        outcome = "NEEDS_HUMAN_REVIEW"
        outcome_explanation = (
            "Submission requires human review due to ambiguous content, classification uncertainty, or possible duplicate detection. "
            "An officer must inspect before registration or rejection."
        )
    else:
        outcome = "PASSED"
        outcome_explanation = "All screening criteria and document checks passed. Submission is eligible for case registration."

    return {
        "submission_ref": str(uuid.uuid4())[:8].upper(),
        "screening_outcome": outcome,
        "outcome_explanation": outcome_explanation,
        "screened_at": datetime.now(UTC).isoformat(),
        "screening_version": "1.0",
        "model_type": "rule_based_with_neural_document_intelligence",
        "disclaimer": (
            "Screening utilizes rule-based validation, pypdf/PIL file extraction, and sentence-transformer neural classification. "
            "Not a trained predictive model. All rejection decisions require administrative confirmation."
        ),
        "failures": failures,
        "human_review_triggers": human_review_triggers,
        "document_screening": document_screening_results,
        "criteria_checked": 10 if has_file_input else 6,
        "institution_resolved": institution.name if institution else None,
        "institution_id": institution.id if institution else None,
        "passed": outcome == "PASSED",
    }

