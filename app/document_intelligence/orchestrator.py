"""Orchestrator for AI Document Intelligence & Pre-Scrutiny Pipeline.

Coordinates document classification, structured field extraction, regulatory validation,
deficiency notice generation, and database persistence.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.enums import ActionType, AlertSeverity, CaseStatus
from app.models import (
    Alert,
    AuditEvent,
    Case,
    CaseEvent,
    DocumentAnalysis,
    DocumentAnalysisReview,
    Institution,
    User,
)
from app.document_intelligence.classifier import classify_document
from app.document_intelligence.deficiency_generator import (
    generate_deficiency_notice,
)
from app.document_intelligence.model_provider import (
    extract_document_fields,
)
from app.document_intelligence.schemas import (
    AlternativeCategory,
    CorrectionApprovalRequest,
    DocumentAnalysisCreate,
    DocumentAnalysisResponse,
    DocumentCategory,
    DocumentReanalysisCreate,
    ExtractedField,
    FindingSeverity,
    FindingType,
    PreScrutinyStatus,
    ReviewSubmission,
    ValidationFinding,
)
from app.document_intelligence.validator import validate_document

logger = logging.getLogger(__name__)


def _to_response_dto(da: DocumentAnalysis) -> DocumentAnalysisResponse:
    """Converts a DocumentAnalysis ORM object into a Pydantic response DTO."""
    extracted_fields_dto = {
        k: ExtractedField(**v) if isinstance(v, dict) else v
        for k, v in (da.extracted_fields or {}).items()
    }
    findings_dto = [
        ValidationFinding(**f) if isinstance(f, dict) else f
        for f in (da.findings or [])
    ]
    top_alts_dto = [
        AlternativeCategory(**a) if isinstance(a, dict) else a
        for a in (da.top_alternatives or [])
    ]
    reviews_dto = [
        {
            "id": r.id,
            "review_action": r.review_action,
            "reviewer_comments": r.reviewer_comments,
            "final_review_status": r.final_review_status,
            "reviewer_name": r.reviewer.full_name if r.reviewer else "Scrutiny Officer",
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in da.reviews
    ]

    return DocumentAnalysisResponse(
        id=da.id,
        case_id=da.case_id,
        case_numeric_id=da.case_numeric_id,
        institution_id=da.institution_id,
        institution_name=da.institution.name if da.institution else "Unknown Institution",
        document_type=da.document_type,
        input_source=da.input_source,
        ocr_text_reference=da.fixture_id,
        ocr_text_snippet=da.ocr_text_snippet,
        extracted_fields=extracted_fields_dto,
        field_evidence=da.field_evidence or {},
        findings=findings_dto,
        classification_confidence=da.classification_confidence,
        top_alternatives=top_alts_dto,
        classification_method=da.classification_method,
        model_name=da.model_name,
        analysis_version=da.analysis_version,
        parent_analysis_id=da.parent_analysis_id,
        pre_scrutiny_status=PreScrutinyStatus(da.pre_scrutiny_status),
        recommended_action=da.recommended_action,
        requires_human_review=da.requires_human_review,
        generated_deficiency_message=da.generated_deficiency_message,
        duration_ms=da.duration_ms,
        created_at=da.created_at,
        updated_at=da.updated_at,
        reviews=reviews_dto,
    )


def run_pipeline(
    case: Case,
    ocr_text: str,
    document_type_hint: str | None = None,
    academic_year: str | None = None,
    fixture_id: str | None = None,
    input_source: str = "manual_ocr",
    version: int = 1,
    parent_analysis_id: int | None = None,
    db: Session | None = None,
) -> DocumentAnalysis:
    """Executes the complete Document Intelligence and Pre-Scrutiny pipeline."""
    start_time = time.perf_counter()

    # 1. Classification via sentence-transformers neural model
    classification_res = classify_document(ocr_text)
    determined_category = classification_res.category

    # If hint provided and matches a valid category, but model classified differently with low confidence, consider hint
    if document_type_hint and classification_res.confidence < 0.50:
        for cat in DocumentCategory:
            if cat.value.lower() == document_type_hint.lower():
                determined_category = cat
                break

    # 2. Structured field extraction (deterministic regex semantic fallback or Ollama)
    extracted_fields, extraction_method, extraction_model = extract_document_fields(
        ocr_text, determined_category
    )

    # 3. Validation and decision engine
    case_context = {
        "case_id": case.case_id,
        "institution_id": case.institution_id,
        "institution_name": case.institution.name if case.institution else "",
        "institution_identifier": case.institution.permanent_id if case.institution else "",
        "academic_year": academic_year or "2024-25",
    }

    status, findings, recommended_action, needs_review = validate_document(
        category=determined_category,
        extracted_fields=extracted_fields,
        case_context=case_context,
        ocr_text=ocr_text,
        classification_confidence=classification_res.confidence,
        requires_classification_review=classification_res.requires_human_review,
    )

    # 4. Generate official deficiency notice if document is FLAGGED
    deficiency_notice = generate_deficiency_notice(
        case_id=case.case_id,
        institution_name=case.institution.name if case.institution else "Institution",
        institution_identifier=case.institution.permanent_id if case.institution else None,
        document_type=determined_category.value,
        findings=findings,
    )

    duration_ms = int((time.perf_counter() - start_time) * 1000)

    # Build field evidence map
    field_evidence_map = {
        k: f.evidence for k, f in extracted_fields.items() if f.evidence
    }

    # Snippet for preview
    snippet = ocr_text[:300].replace("\n", " ").strip()
    if len(ocr_text) > 300:
        snippet += "..."

    # Create and persist DocumentAnalysis
    da = DocumentAnalysis(
        case_numeric_id=case.id,
        case_id=case.case_id,
        institution_id=case.institution_id,
        document_type=determined_category.value,
        input_source=input_source,
        fixture_id=fixture_id,
        ocr_text=ocr_text,
        ocr_text_snippet=snippet,
        extracted_fields={k: v.model_dump() for k, v in extracted_fields.items()},
        field_evidence=field_evidence_map,
        findings=[f.model_dump() for f in findings],
        classification_confidence=classification_res.confidence,
        top_alternatives=[a.model_dump() for a in classification_res.top_alternatives],
        classification_method=classification_res.classification_method,
        model_name=classification_res.model_name,
        analysis_version=version,
        parent_analysis_id=parent_analysis_id,
        pre_scrutiny_status=status.value,
        recommended_action=recommended_action,
        requires_human_review=needs_review,
        generated_deficiency_message=deficiency_notice,
        duration_ms=duration_ms,
    )

    if db:
        db.add(da)
        db.commit()
        db.refresh(da)

    return da


def analyze_document_submission(
    payload: DocumentAnalysisCreate,
    current_user: User | None,
    db: Session,
) -> DocumentAnalysisResponse:
    """Entry point for initial document analysis submission."""
    # Find case
    case = db.query(Case).filter(Case.case_id == payload.case_id).first()
    if not case:
        if payload.case_id.startswith("CASE-INTAKE"):
            case = db.query(Case).first()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case with ID '{payload.case_id}' not found.",
            )

    da = run_pipeline(
        case=case,
        ocr_text=payload.ocr_text,
        document_type_hint=payload.document_type,
        academic_year=payload.academic_year,
        fixture_id=payload.fixture_id,
        input_source=payload.input_source,
        version=1,
        parent_analysis_id=None,
        db=db,
    )

    # Log audit event
    audit = AuditEvent(
        entity_type="document_analysis",
        entity_id=str(da.id),
        action="DOCUMENT_ANALYZED",
        actor_id=current_user.id if current_user else None,
        details={
            "case_id": case.case_id,
            "document_type": da.document_type,
            "pre_scrutiny_status": da.pre_scrutiny_status,
            "findings_count": len(da.findings),
            "confidence": da.classification_confidence,
        },
    )
    db.add(audit)
    db.commit()

    return _to_response_dto(da)


def reanalyze_document_submission(
    analysis_id: int,
    payload: DocumentReanalysisCreate,
    current_user: User | None,
    db: Session,
) -> DocumentAnalysisResponse:
    """Reanalyzes an amended/resubmitted document and creates a version 2 analysis linked to parent."""
    parent_da = db.query(DocumentAnalysis).filter(DocumentAnalysis.id == analysis_id).first()
    if not parent_da:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis with ID {analysis_id} not found.",
        )

    case = parent_da.case
    new_version = parent_da.analysis_version + 1

    child_da = run_pipeline(
        case=case,
        ocr_text=payload.ocr_text,
        document_type_hint=parent_da.document_type,
        fixture_id=f"{parent_da.fixture_id}-RESUBMISSION" if parent_da.fixture_id else None,
        input_source="resubmission_ocr",
        version=new_version,
        parent_analysis_id=parent_da.id,
        db=db,
    )

    # Record review entry for parent linking
    review = DocumentAnalysisReview(
        analysis_id=parent_da.id,
        reviewer_user_id=current_user.id if current_user else None,
        review_action="reanalyzed_resubmission",
        reviewer_comments=payload.reviewer_comments or f"Resubmitted corrected version #{new_version}.",
        finding_updates=[],
        final_review_status="SUPERSEDED",
    )
    db.add(review)

    # If the case was PENDING_INSTITUTION_RESPONSE and new status is PASSED, transition case to UNDER_PROCESS
    if case.status == CaseStatus.PENDING_INSTITUTION_RESPONSE:
        case.status = CaseStatus.UNDER_PROCESS
        case.last_action = f"Institution resubmitted document; Pre-scrutiny verdict: {child_da.pre_scrutiny_status}"
        case.last_action_at = datetime.now()

        event = CaseEvent(
            case_id=case.id,
            action_type=ActionType.STATUS_CHANGED,
            actor_id=current_user.id if current_user else None,
            previous_values={"status": CaseStatus.PENDING_INSTITUTION_RESPONSE.value},
            new_values={"status": CaseStatus.UNDER_PROCESS.value},
            remarks=f"Document resubmission analyzed. New Pre-scrutiny status: {child_da.pre_scrutiny_status}.",
        )
        db.add(event)

    audit = AuditEvent(
        entity_type="document_analysis",
        entity_id=str(child_da.id),
        action="DOCUMENT_REANALYZED",
        actor_id=current_user.id if current_user else None,
        details={
            "parent_analysis_id": parent_da.id,
            "version": new_version,
            "status": child_da.pre_scrutiny_status,
        },
    )
    db.add(audit)
    db.commit()

    return _to_response_dto(child_da)


def review_findings(
    analysis_id: int,
    submission: ReviewSubmission,
    current_user: User | None,
    db: Session,
) -> DocumentAnalysisResponse:
    """Updates findings confirmation/dismissal status based on scrutiny officer review."""
    da = db.query(DocumentAnalysis).filter(DocumentAnalysis.id == analysis_id).first()
    if not da:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis with ID {analysis_id} not found.",
        )

    current_findings = list(da.findings or [])
    finding_map = {f["finding_id"]: f for f in current_findings}

    for update in submission.finding_updates:
        if update.finding_id in finding_map:
            f = finding_map[update.finding_id]
            if update.confirmed is not None:
                f["confirmed_by_admin"] = update.confirmed
            if update.dismissed:
                f["dismissed"] = True
            if update.admin_note:
                f["admin_note"] = update.admin_note

    da.findings = list(finding_map.values())

    # Recalculate status if all critical findings are dismissed
    remaining_active_critical = any(
        f.get("severity") == FindingSeverity.CRITICAL.value and not f.get("dismissed")
        for f in da.findings
    )
    if not remaining_active_critical and da.pre_scrutiny_status == PreScrutinyStatus.FLAGGED.value:
        da.pre_scrutiny_status = PreScrutinyStatus.PASSED.value
        da.recommended_action = "All critical deficiencies were reviewed and dismissed by the scrutiny officer. Cleared for processing."

    if submission.final_review_status:
        da.pre_scrutiny_status = submission.final_review_status

    review_record = DocumentAnalysisReview(
        analysis_id=da.id,
        reviewer_user_id=current_user.id if current_user else None,
        review_action=submission.review_action,
        reviewer_comments=submission.reviewer_comments,
        finding_updates=[u.model_dump() for u in submission.finding_updates],
        final_review_status=submission.final_review_status or da.pre_scrutiny_status,
    )
    db.add(review_record)
    db.commit()
    db.refresh(da)

    return _to_response_dto(da)


def approve_correction_request(
    analysis_id: int,
    req: CorrectionApprovalRequest,
    current_user: User | None,
    db: Session,
) -> dict[str, Any]:
    """Approves sending a deficiency notice to the institution:
    - Transitions case status to PENDING_INSTITUTION_RESPONSE
    - Logs CaseEvent
    - Creates an Alert
    - Records an AuditEvent
    """
    da = db.query(DocumentAnalysis).filter(DocumentAnalysis.id == analysis_id).first()
    if not da:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis with ID {analysis_id} not found.",
        )

    case = da.case
    prev_status = case.status

    # Update case status
    case.status = CaseStatus.PENDING_INSTITUTION_RESPONSE
    case.last_action = f"Pre-scrutiny deficiency notice issued for {da.document_type}"
    case.last_action_at = datetime.now()
    case.next_action = "Awaiting institutional response/document rectification (7 days)"

    # Create CaseEvent
    case_event = CaseEvent(
        case_id=case.id,
        action_type=ActionType.STATUS_CHANGED,
        actor_id=current_user.id if current_user else None,
        bureau_id=case.current_bureau_id,
        previous_values={"status": prev_status.value},
        new_values={"status": CaseStatus.PENDING_INSTITUTION_RESPONSE.value},
        remarks=f"Scrutiny officer approved deficiency notice for {da.document_type}.",
    )
    db.add(case_event)

    # Create Alert
    dedupe_key = f"alert_deficiency_{case.case_id}_{da.id}_{int(time.time())}"
    alert = Alert(
        dedupe_key=dedupe_key,
        alert_type="PRE_SCRUTINY_DEFICIENCY",
        severity=AlertSeverity.CRITICAL,
        title=f"Pre-Scrutiny Deficiencies Flagged: {case.case_id}",
        message=f"Deficiencies detected in '{da.document_type}' for {case.institution.name}. Notice dispatched.",
        case_id=case.id,
        bureau_id=case.current_bureau_id,
        region=case.institution.region if case.institution else None,
    )
    db.add(alert)

    # Create DocumentAnalysisReview record
    review = DocumentAnalysisReview(
        analysis_id=da.id,
        reviewer_user_id=current_user.id if current_user else None,
        review_action="approve_correction",
        reviewer_comments=req.reviewer_comments or "Deficiency notice approved and dispatched to institution.",
        finding_updates=[],
        final_review_status="CORRECTION_NOTICE_ISSUED",
    )
    db.add(review)

    # Update saved deficiency message if edited
    da.generated_deficiency_message = req.deficiency_message

    # Record AuditEvent
    audit = AuditEvent(
        entity_type="document_analysis",
        entity_id=str(da.id),
        action="DEFICIENCY_NOTICE_DISPATCHED",
        actor_id=current_user.id if current_user else None,
        details={
            "case_id": case.case_id,
            "document_type": da.document_type,
            "previous_status": prev_status.value,
            "new_status": CaseStatus.PENDING_INSTITUTION_RESPONSE.value,
        },
    )
    db.add(audit)
    db.commit()

    return {
        "success": True,
        "message": f"Deficiency notice successfully dispatched to {case.institution.name}.",
        "case_id": case.case_id,
        "new_case_status": CaseStatus.PENDING_INSTITUTION_RESPONSE.value,
        "deficiency_message": req.deficiency_message,
    }


def get_case_analyses(case_id: str, db: Session) -> list[DocumentAnalysisResponse]:
    """Retrieves all document analyses associated with a case."""
    analyses = (
        db.query(DocumentAnalysis)
        .filter(DocumentAnalysis.case_id == case_id)
        .order_by(DocumentAnalysis.created_at.desc())
        .all()
    )
    return [_to_response_dto(a) for a in analyses]


def get_analysis_by_id(analysis_id: int, db: Session) -> DocumentAnalysisResponse | None:
    """Retrieves a single document analysis by ID."""
    da = db.query(DocumentAnalysis).filter(DocumentAnalysis.id == analysis_id).first()
    if not da:
        return None
    return _to_response_dto(da)
