"""API Router for AI Document Intelligence & Automated Pre-Scrutiny."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.document_intelligence.file_extractor import extract_content_from_file_bytes
from app.document_intelligence.fixtures import (
    get_all_fixtures,
    get_demo_scenarios,
    get_fixture_by_id,
)
from app.document_intelligence.orchestrator import (
    analyze_document_submission,
    approve_correction_request,
    get_analysis_by_id,
    get_case_analyses,
    reanalyze_document_submission,
    review_findings,
)
from app.document_intelligence.schemas import (
    CorrectionApprovalRequest,
    DocumentAnalysisCreate,
    DocumentAnalysisResponse,
    DocumentReanalysisCreate,
    ReviewSubmission,
)

router = APIRouter(prefix="/api/document-intelligence", tags=["document-intelligence"])


# =============================================================================
# SYNTHETIC FIXTURE LIBRARY ENDPOINTS
# =============================================================================

@router.get("/fixtures")
def list_fixtures(
    category: str | None = None,
    scenario: str | None = None,
    demo_only: bool = False,
) -> list[dict[str, Any]]:
    """Lists synthetic OCR fixtures with filtering by category, scenario, or demo flag."""
    fixtures = get_all_fixtures()
    if demo_only:
        fixtures = [f for f in fixtures if f.get("is_demo_scenario")]
    if category:
        fixtures = [f for f in fixtures if f["category"].value == category or f["category"] == category]
    if scenario:
        fixtures = [f for f in fixtures if f["scenario"].lower() == scenario.lower()]

    # Return preview metadata (avoiding full text in index if list is large)
    return [
        {
            "fixture_id": f["fixture_id"],
            "category": f["category"].value if hasattr(f["category"], "value") else str(f["category"]),
            "scenario": f["scenario"],
            "is_demo_scenario": f.get("is_demo_scenario", False),
            "demo_title": f.get("demo_title"),
            "institution_name": f["institution_name"],
            "institution_identifier": f["institution_identifier"],
            "associated_case_id": f.get("associated_case_id"),
            "academic_year": f.get("academic_year"),
            "description": f["description"],
            "expected_classification": f["expected_classification"],
            "expected_pre_scrutiny_status": f["expected_pre_scrutiny_status"],
            "ocr_text_preview": f["ocr_text"][:160].replace("\n", " ") + "...",
        }
        for f in fixtures
    ]


@router.get("/fixtures/{fixture_id}")
def get_fixture_detail(fixture_id: str) -> dict[str, Any]:
    """Retrieves complete fixture record including full OCR text."""
    fixture = get_fixture_by_id(fixture_id)
    if not fixture:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fixture '{fixture_id}' not found in synthetic document library.",
        )
    return {
        "fixture_id": fixture["fixture_id"],
        "category": fixture["category"].value if hasattr(fixture["category"], "value") else str(fixture["category"]),
        "scenario": fixture["scenario"],
        "is_demo_scenario": fixture.get("is_demo_scenario", False),
        "demo_title": fixture.get("demo_title"),
        "institution_name": fixture["institution_name"],
        "institution_identifier": fixture["institution_identifier"],
        "associated_case_id": fixture.get("associated_case_id"),
        "academic_year": fixture.get("academic_year"),
        "description": fixture["description"],
        "expected_classification": fixture["expected_classification"],
        "expected_pre_scrutiny_status": fixture["expected_pre_scrutiny_status"],
        "expected_recommended_action": fixture["expected_recommended_action"],
        "ocr_text": fixture["ocr_text"],
    }


@router.get("/demo-scenarios")
def list_demo_scenarios() -> list[dict[str, Any]]:
    """Returns the 8 mandatory end-to-end demonstration scenarios."""
    scenarios = get_demo_scenarios()
    return [
        {
            "fixture_id": f["fixture_id"],
            "demo_title": f.get("demo_title"),
            "category": f["category"].value if hasattr(f["category"], "value") else str(f["category"]),
            "scenario": f["scenario"],
            "institution_name": f["institution_name"],
            "institution_identifier": f["institution_identifier"],
            "associated_case_id": f.get("associated_case_id"),
            "expected_status": f["expected_pre_scrutiny_status"],
            "description": f["description"],
            "ocr_text": f["ocr_text"],
        }
        for f in scenarios
    ]


# =============================================================================
# DOCUMENT ANALYSIS PIPELINE ENDPOINTS
# =============================================================================

@router.post("/analyze", response_model=DocumentAnalysisResponse)
def analyze_document(
    payload: DocumentAnalysisCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentAnalysisResponse:
    """Submits OCR document text to the AI Pre-Scrutiny pipeline."""
    return analyze_document_submission(payload, current_user, db)


@router.post("/upload-and-analyze", response_model=DocumentAnalysisResponse)
async def upload_and_analyze_document(
    file: UploadFile = File(...),
    case_id: str = Form("CASE-INTAKE-PRE-SCRUTINY"),
    academic_year: str | None = Form(None),
    document_type_hint: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentAnalysisResponse:
    """
    Uploads a real file (PDF, PNG, JPG, TXT) and processes it through the AI Document Intelligence pipeline.
    Extracts text using pypdf/PIL, performs neural classification, and runs regulatory validation.
    """
    file_bytes = await file.read()
    extracted = extract_content_from_file_bytes(
        file_bytes=file_bytes,
        filename=file.filename or "uploaded_file",
        content_type=file.content_type,
    )

    if not extracted.is_readable or extracted.is_corrupted:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Document upload could not be processed: {extracted.error_message or 'Unreadable/corrupted file.'}",
        )

    if len(extracted.text.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Document text length is insufficient for AI pre-scrutiny (minimum 10 characters required).",
        )

    payload = DocumentAnalysisCreate(
        case_id=case_id,
        ocr_text=extracted.text,
        academic_year=academic_year,
        document_type=document_type_hint,
        input_source=f"upload_{extracted.filename.split('.')[-1].lower()}",
    )
    return analyze_document_submission(payload, current_user, db)


@router.get("/results/{analysis_id}", response_model=DocumentAnalysisResponse)
def get_analysis_result(
    analysis_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentAnalysisResponse:
    """Retrieves document pre-scrutiny analysis result by ID."""
    res = get_analysis_by_id(analysis_id, db)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis with ID {analysis_id} not found.",
        )
    return res


@router.get("/cases/{case_id}", response_model=list[DocumentAnalysisResponse])
def get_analyses_for_case(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DocumentAnalysisResponse]:
    """Retrieves all document analysis records for a case."""
    return get_case_analyses(case_id, db)


@router.post("/results/{analysis_id}/review", response_model=DocumentAnalysisResponse)
def review_analysis_findings(
    analysis_id: int,
    submission: ReviewSubmission,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentAnalysisResponse:
    """Administrative review of AI findings (confirm, dismiss, notes)."""
    return review_findings(analysis_id, submission, current_user, db)


@router.post("/results/{analysis_id}/request-correction")
def send_correction_request(
    analysis_id: int,
    payload: CorrectionApprovalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Approves sending official AICTE Pre-Scrutiny deficiency notice.
    
    Transitions case to PENDING_INSTITUTION_RESPONSE, creates an Alert,
    and logs CaseEvent and AuditEvent.
    """
    return approve_correction_request(analysis_id, payload, current_user, db)


@router.post("/results/{analysis_id}/reanalyze", response_model=DocumentAnalysisResponse)
def reanalyze_document(
    analysis_id: int,
    payload: DocumentReanalysisCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentAnalysisResponse:
    """Submits a revised/corrected document version for reanalysis.
    
    Creates a new analysis version linked to the parent analysis.
    """
    return reanalyze_document_submission(analysis_id, payload, current_user, db)
