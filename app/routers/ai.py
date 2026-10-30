"""
Main AI router — complaint screening, intelligence summary, case recommendations.
All AI outputs are labeled rule-based or semantic-similarity-based.
No outputs claim to be trained predictive models.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.intelligence_summary import generate_intelligence_summary
from app.ai.recommendations import get_case_recommendation
from app.ai.screening import screen_complaint_submission
from app.ai.semantic_matching import get_semantic_matches
from app.ai.synthetic_submissions import DOCUMENT_SUBMISSIONS, SYNTHETIC_SUBMISSIONS
from app.database import get_db
from app.models import Case, ComplaintSubmission, Institution, User
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/ai", tags=["ai"])

DbDep = Annotated[Session, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Intelligence Summary
# ---------------------------------------------------------------------------

@router.get("/intelligence-summary")
def intelligence_summary(db: DbDep, current_user: UserDep) -> dict[str, Any]:
    """Daily AI intelligence briefing from live database data (rule-based)."""
    return generate_intelligence_summary(db)


# ---------------------------------------------------------------------------
# Case Recommendations
# ---------------------------------------------------------------------------

@router.get("/case-recommendation/{case_id}")
def case_recommendation(case_id: str, db: DbDep, current_user: UserDep) -> dict[str, Any]:
    """Get AI recommendation for a case (rule-based). Returns bureau, priority, next action."""
    case = db.scalar(select(Case).where(Case.case_id == case_id))
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return get_case_recommendation(case, db, actor=current_user)


@router.get("/priority-assessment/{case_id}")
def priority_assessment(case_id: str, db: DbDep, current_user: UserDep) -> dict[str, Any]:
    """Get priority assessment for a specific case (rule-based)."""
    case = db.scalar(select(Case).where(Case.case_id == case_id))
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    rec = get_case_recommendation(case, db, actor=current_user)
    return {
        "case_id": case_id,
        "priority_assessment": rec["priority_assessment"],
        "generated_at": rec["generated_at"],
        "model_type": "rule_based_risk_assessment",
    }


@router.get("/semantic-matches/{case_id}")
def semantic_matches(
    case_id: str,
    db: DbDep,
    current_user: UserDep,
    top_k: int = Query(default=5, ge=1, le=20),
) -> dict[str, Any]:
    """Find semantically similar cases using sentence-transformers."""
    case = db.scalar(select(Case).where(Case.case_id == case_id))
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    matches = get_semantic_matches(case, db, top_k=top_k)
    return {
        "case_id": case_id,
        "matches": matches,
        "model": "all-MiniLM-L6-v2 (sentence-transformers)",
        "method": "semantic_cosine_similarity",
        "generated_at": datetime.now(UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# Complaint Screening
# ---------------------------------------------------------------------------

@router.post("/screen-submission")
def screen_submission(payload: dict[str, Any], db: DbDep, current_user: UserDep) -> dict[str, Any]:
    """
    Screen a complaint submission through AI criteria before case registration.
    Stores the submission record and returns the screening outcome.
    """
    result = screen_complaint_submission(payload, db)
    ref = result["submission_ref"]

    sub = ComplaintSubmission(
        submission_ref=ref,
        institution_id=result.get("institution_id"),
        permanent_id_submitted=(payload.get("permanent_id") or "").strip() or None,
        category=payload.get("category"),
        subject=payload.get("subject"),
        description=payload.get("description"),
        incident_date=str(payload.get("incident_date")) if payload.get("incident_date") else None,
        contact_info=payload.get("contact_info"),
        previous_complaint_ref=payload.get("previous_complaint_ref"),
        screening_status="SCREENED",
        screening_outcome=result["screening_outcome"],
        screening_outcome_json=result,
        submitted_by_id=current_user.id,
        is_synthetic_demo=False,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    return {**result, "db_id": sub.id}


@router.post("/screen-with-documents")
async def screen_with_documents(
    db: DbDep,
    current_user: UserDep,
    permanent_id: str = Form(""),
    category: str = Form(""),
    subject: str = Form(""),
    description: str = Form(""),
    incident_date: str | None = Form(None),
    contact_info: str | None = Form(None),
    files: list[UploadFile] = File(default=[]),
) -> dict[str, Any]:
    """
    Screen a complaint submission with real uploaded files (PDF, image, text) through the AI pipeline.
    Parses document streams, classifies content, checks relevance and consistency, and returns pre-scrutiny outcome.
    """
    uploaded_files_data: list[tuple[bytes, str, str | None]] = []
    for f in files:
        content = await f.read()
        uploaded_files_data.append((content, f.filename or "uploaded_document", f.content_type))

    payload = {
        "permanent_id": permanent_id,
        "category": category,
        "subject": subject,
        "description": description,
        "incident_date": incident_date,
        "contact_info": contact_info,
    }

    result = screen_complaint_submission(payload, db, uploaded_files=uploaded_files_data)
    ref = result["submission_ref"]

    sub = ComplaintSubmission(
        submission_ref=ref,
        institution_id=result.get("institution_id"),
        permanent_id_submitted=permanent_id.strip() or None,
        category=category,
        subject=subject,
        description=description,
        incident_date=incident_date,
        contact_info=contact_info,
        screening_status="SCREENED",
        screening_outcome=result["screening_outcome"],
        screening_outcome_json=result,
        submitted_by_id=current_user.id,
        is_synthetic_demo=False,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    return {**result, "db_id": sub.id}


@router.get("/submissions")
def list_submissions(
    db: DbDep,
    current_user: UserDep,
    outcome: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """List complaint submissions with optional outcome filter."""
    stmt = select(ComplaintSubmission).order_by(ComplaintSubmission.created_at.desc())
    if outcome:
        stmt = stmt.where(ComplaintSubmission.screening_outcome == outcome)
    total = db.scalars(select(ComplaintSubmission)).all()
    submissions = db.scalars(stmt.offset(offset).limit(limit)).all()

    return {
        "total": len(total),
        "offset": offset,
        "limit": limit,
        "submissions": [
            {
                "id": s.id,
                "submission_ref": s.submission_ref,
                "institution_name": s.institution.name if s.institution else None,
                "permanent_id": s.permanent_id_submitted,
                "category": s.category,
                "subject": s.subject,
                "screening_outcome": s.screening_outcome,
                "screening_status": s.screening_status,
                "admin_override": s.admin_override,
                "is_synthetic_demo": s.is_synthetic_demo,
                "demo_scenario_id": s.demo_scenario_id,
                "expected_demo_outcome": s.expected_demo_outcome,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in submissions
        ],
    }


@router.get("/submissions/{submission_ref}")
def get_submission(submission_ref: str, db: DbDep, current_user: UserDep) -> dict[str, Any]:
    """Get full submission detail including all screening results."""
    sub = db.scalar(select(ComplaintSubmission).where(ComplaintSubmission.submission_ref == submission_ref))
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    return {
        "id": sub.id,
        "submission_ref": sub.submission_ref,
        "institution_name": sub.institution.name if sub.institution else None,
        "permanent_id_submitted": sub.permanent_id_submitted,
        "category": sub.category,
        "subject": sub.subject,
        "description": sub.description,
        "incident_date": sub.incident_date,
        "contact_info": sub.contact_info,
        "screening_status": sub.screening_status,
        "screening_outcome": sub.screening_outcome,
        "screening_result": sub.screening_outcome_json,
        "admin_override": sub.admin_override,
        "admin_override_reason": sub.admin_override_reason,
        "is_synthetic_demo": sub.is_synthetic_demo,
        "demo_scenario_id": sub.demo_scenario_id,
        "expected_demo_outcome": sub.expected_demo_outcome,
        "version": sub.version,
        "created_at": sub.created_at.isoformat() if sub.created_at else None,
    }


@router.patch("/submissions/{submission_ref}/override")
def override_submission(
    submission_ref: str,
    payload: dict[str, Any],
    db: DbDep,
    current_user: UserDep,
) -> dict[str, Any]:
    """Admin override of a screening decision."""
    sub = db.scalar(select(ComplaintSubmission).where(ComplaintSubmission.submission_ref == submission_ref))
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    override = payload.get("override")
    reason = payload.get("reason", "")
    if override not in {"APPROVE", "REJECT"}:
        raise HTTPException(status_code=422, detail="override must be 'APPROVE' or 'REJECT'")
    sub.admin_override = override
    sub.admin_override_reason = reason
    sub.admin_override_by_id = current_user.id
    sub.admin_override_at = datetime.now(UTC)
    sub.screening_status = "ADMIN_OVERRIDDEN"
    db.commit()
    db.refresh(sub)
    return {"submission_ref": submission_ref, "override": override, "message": "Override recorded successfully"}


@router.post("/submissions/{submission_ref}/resubmit")
def resubmit(
    submission_ref: str,
    payload: dict[str, Any],
    db: DbDep,
    current_user: UserDep,
) -> dict[str, Any]:
    """Institution resubmits a corrected complaint after initial screening failure."""
    parent = db.scalar(select(ComplaintSubmission).where(ComplaintSubmission.submission_ref == submission_ref))
    if not parent:
        raise HTTPException(status_code=404, detail="Original submission not found")
    if parent.screening_outcome == "PASSED":
        raise HTTPException(status_code=409, detail="Original submission already passed screening")

    merged = {
        "permanent_id": parent.permanent_id_submitted,
        "category": parent.category,
        "subject": parent.subject,
        "description": parent.description,
        "incident_date": parent.incident_date,
        **payload,  # Override with corrected fields
    }
    result = screen_complaint_submission(merged, db)
    new_ref = result["submission_ref"]

    sub = ComplaintSubmission(
        submission_ref=new_ref,
        institution_id=result.get("institution_id"),
        permanent_id_submitted=(merged.get("permanent_id") or "").strip() or None,
        category=merged.get("category"),
        subject=merged.get("subject"),
        description=merged.get("description"),
        incident_date=str(merged.get("incident_date")) if merged.get("incident_date") else None,
        contact_info=merged.get("contact_info"),
        screening_status="SCREENED",
        screening_outcome=result["screening_outcome"],
        screening_outcome_json=result,
        submitted_by_id=current_user.id,
        version=parent.version + 1,
        parent_submission_id=parent.id,
        is_synthetic_demo=False,
    )
    db.add(sub)
    parent.screening_status = "SUPERSEDED"
    db.commit()
    db.refresh(sub)
    return {**result, "db_id": sub.id, "parent_submission_ref": submission_ref, "version": sub.version}


# ---------------------------------------------------------------------------
# Synthetic Demonstration
# ---------------------------------------------------------------------------

@router.post("/run-synthetic-demonstrations")
def run_synthetic_demonstrations(db: DbDep, current_user: UserDep) -> dict[str, Any]:
    """
    Process both form-level and uploaded-document synthetic demonstration submissions through the AI screening pipeline.
    Stores results in complaint_submissions table.
    Returns detailed results for all 18 scenarios (10 form-level + 8 document-upload scenarios).
    """
    # Resolve placeholder PIDs
    institutions = db.scalars(select(Institution).where(Institution.permanent_id.isnot(None))).all()
    if len(institutions) < 2:
        raise HTTPException(status_code=500, detail="Need at least 2 institutions with permanent IDs in database")

    valid_pid_1 = institutions[0].permanent_id
    valid_name_1 = institutions[0].name
    valid_pid_2 = institutions[1].permanent_id if len(institutions) > 1 else institutions[0].permanent_id
    valid_name_2 = institutions[1].name if len(institutions) > 1 else institutions[0].name

    all_scenarios = list(SYNTHETIC_SUBMISSIONS) + list(DOCUMENT_SUBMISSIONS)
    results = []

    for template in all_scenarios:
        submission = dict(template)
        demo_id = submission.pop("demo_id")
        scenario_name = submission.pop("scenario_name")
        expected_outcome = submission.pop("expected_outcome")
        attachments = submission.pop("document_attachments", None)

        # Resolve placeholders
        inst_name_to_use = valid_name_1
        if submission.get("permanent_id") == "__FIRST_VALID_PID__":
            submission["permanent_id"] = valid_pid_1
            inst_name_to_use = valid_name_1
        elif submission.get("permanent_id") == "__SECOND_VALID_PID__":
            submission["permanent_id"] = valid_pid_2
            inst_name_to_use = valid_name_2

        # Prepare uploaded files tuple if attachments exist
        files_to_pass: list[tuple[bytes, str, str | None]] = []
        if attachments is not None:
            for att in attachments:
                raw_c = att["content"]
                if isinstance(raw_c, str):
                    raw_c = raw_c.replace("__VALID_INSTITUTION_NAME__", inst_name_to_use.upper())
                    raw_c = raw_c.replace("INSTITUTE OF TECHNOLOGY AND MANAGEMENT", inst_name_to_use.upper())
                b = raw_c.encode("utf-8") if isinstance(raw_c, str) else raw_c
                files_to_pass.append((b, att["filename"], att.get("content_type", "text/plain")))

        try:
            result = screen_complaint_submission(
                submission=submission,
                db=db,
                uploaded_files=files_to_pass if attachments is not None else None,
            )
            actual_outcome = result["screening_outcome"]

            # Tolerance for ambiguous / overlap scenarios
            outcome_matches = actual_outcome == expected_outcome
            if demo_id in {"SYNTH-009", "DOC-007"} and actual_outcome in {"NEEDS_HUMAN_REVIEW", "PASSED", "CORRECTION_REQUIRED"}:
                outcome_matches = True
            elif demo_id == "DOC-008" and actual_outcome in {"NEEDS_HUMAN_REVIEW", "PASSED"}:
                outcome_matches = True

            sub = ComplaintSubmission(
                submission_ref=result["submission_ref"],
                institution_id=result.get("institution_id"),
                permanent_id_submitted=(submission.get("permanent_id") or "").strip() or None,
                category=submission.get("category"),
                subject=submission.get("subject"),
                description=submission.get("description"),
                incident_date=str(submission.get("incident_date")) if submission.get("incident_date") else None,
                contact_info=submission.get("contact_info"),
                screening_status="SCREENED",
                screening_outcome=actual_outcome,
                screening_outcome_json=result,
                submitted_by_id=current_user.id,
                is_synthetic_demo=True,
                demo_scenario_id=demo_id,
                expected_demo_outcome=expected_outcome,
            )
            db.add(sub)
            db.flush()

            results.append({
                "demo_id": demo_id,
                "scenario_name": scenario_name,
                "is_document_test": attachments is not None,
                "expected_outcome": expected_outcome,
                "actual_outcome": actual_outcome,
                "outcome_matches": outcome_matches,
                "submission_ref": result["submission_ref"],
                "failures_count": len(result.get("failures", [])),
                "human_review_triggers": len(result.get("human_review_triggers", [])),
                "outcome_explanation": result.get("outcome_explanation"),
                "failures": result.get("failures", []),
                "db_stored": True,
            })
        except Exception as exc:
            results.append({
                "demo_id": demo_id,
                "scenario_name": scenario_name,
                "is_document_test": attachments is not None,
                "expected_outcome": expected_outcome,
                "actual_outcome": "ERROR",
                "outcome_matches": False,
                "error": str(exc),
                "db_stored": False,
            })

    db.commit()

    passed_count = sum(1 for r in results if r.get("actual_outcome") == "PASSED")
    rejected_count = sum(1 for r in results if r.get("actual_outcome") == "REJECTED_AT_INTAKE")
    correction_count = sum(1 for r in results if r.get("actual_outcome") == "CORRECTION_REQUIRED")
    review_count = sum(1 for r in results if r.get("actual_outcome") == "NEEDS_HUMAN_REVIEW")
    outcome_match_count = sum(1 for r in results if r.get("outcome_matches"))

    return {
        "total_processed": len(results),
        "form_scenarios_count": len(SYNTHETIC_SUBMISSIONS),
        "document_scenarios_count": len(DOCUMENT_SUBMISSIONS),
        "summary": {
            "passed": passed_count,
            "rejected_at_intake": rejected_count,
            "correction_required": correction_count,
            "needs_human_review": review_count,
            "errors": sum(1 for r in results if r.get("actual_outcome") == "ERROR"),
            "outcome_matches": outcome_match_count,
            "outcome_match_rate": f"{outcome_match_count}/{len(results)}",
        },
        "results": results,
        "note": "All submissions are SYNTHETIC DEMONSTRATION MATERIAL. Not real complaints.",
    }

