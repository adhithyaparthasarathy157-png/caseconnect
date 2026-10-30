"""Pydantic schemas and enums for AI Document Intelligence & Automated Pre-Scrutiny."""
from datetime import datetime
from enum import StrEnum
from typing import Any
from pydantic import BaseModel, Field


class DocumentCategory(StrEnum):
    # Complaint-related evidence categories (SIH26264 core focus)
    COMPLAINT_LETTER = "Formal Complaint / Grievance Petition"
    FEE_RECEIPT_PAYMENT = "Fee Receipt & Payment Evidence"
    INSTITUTIONAL_NOTICE = "Institutional Notice & Circular"
    APPOINTMENT_TERMINATION = "Appointment / Termination Order"
    FACULTY_EVIDENCE = "Faculty Complaint Evidence / Salary Record"
    CORRESPONDENCE_PROOF = "Correspondence / Representation Proof"
    # Institutional baseline / inspection records
    AFFILIATION_CERTIFICATE = "Affiliation Certificate"
    APPROVAL_LETTER = "Approval Letter"
    INSTITUTION_REGISTRATION = "Institution Registration Certificate"
    FACULTY_STATEMENT = "Faculty Details Statement"
    INFRASTRUCTURE_REPORT = "Infrastructure / Inspection Report"
    UNSUPPORTED = "Unsupported / Unknown Document"


class PreScrutinyStatus(StrEnum):
    PASSED = "PASSED"
    FLAGGED = "FLAGGED"
    NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"
    UNSUPPORTED = "UNSUPPORTED"


class FindingType(StrEnum):
    VALIDATION_FAILURE = "VALIDATION_FAILURE"
    INFORMATION_MISSING = "INFORMATION_MISSING"
    INFORMATION_UNCERTAIN = "INFORMATION_UNCERTAIN"
    HUMAN_VERIFICATION_REQUIRED = "HUMAN_VERIFICATION_REQUIRED"
    UNSUPPORTED_DOCUMENT = "UNSUPPORTED_DOCUMENT"


class FindingSeverity(StrEnum):
    INFO = "Info"
    WARNING = "Warning"
    CRITICAL = "Critical"


class ExtractedField(BaseModel):
    value: Any = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    evidence: str | None = None
    field_type: str = "string"


class ValidationFinding(BaseModel):
    finding_id: str
    field_name: str
    detected_value: Any = None
    expected_condition: str
    finding_type: FindingType
    severity: FindingSeverity
    explanation: str
    evidence_snippet: str | None = None
    suggested_correction: str
    requires_human_review: bool = False
    confirmed_by_admin: bool | None = None
    dismissed: bool = False
    source: str = "ai_extraction"


class AlternativeCategory(BaseModel):
    category: str
    score: float


class DocumentAnalysisCreate(BaseModel):
    case_id: str = Field(default="CASE-INTAKE-PRE-SCRUTINY")
    institution_id: int | None = None
    document_type: str | None = None
    ocr_text: str = Field(min_length=10)
    academic_year: str | None = None
    fixture_id: str | None = None
    input_source: str = "manual_ocr"


class DocumentReanalysisCreate(BaseModel):
    ocr_text: str = Field(min_length=10)
    reviewer_comments: str | None = None


class FindingReviewUpdate(BaseModel):
    finding_id: str
    confirmed: bool | None = None
    dismissed: bool = False
    admin_note: str | None = None


class ReviewSubmission(BaseModel):
    review_action: str  # "confirm", "dismiss_finding", "edit_finding", "manual_verify", "approve_correction"
    reviewer_comments: str | None = None
    finding_updates: list[FindingReviewUpdate] = []
    final_review_status: str | None = None


class CorrectionApprovalRequest(BaseModel):
    deficiency_message: str = Field(min_length=10)
    reviewer_comments: str | None = None


class DocumentAnalysisResponse(BaseModel):
    id: int
    case_id: str
    case_numeric_id: int
    institution_id: int
    institution_name: str
    document_type: str
    input_source: str
    ocr_text_reference: str | None
    ocr_text_snippet: str
    extracted_fields: dict[str, ExtractedField]
    field_evidence: dict[str, str | None]
    findings: list[ValidationFinding]
    classification_confidence: float
    top_alternatives: list[AlternativeCategory]
    classification_method: str
    model_name: str
    analysis_version: int
    parent_analysis_id: int | None
    pre_scrutiny_status: PreScrutinyStatus
    recommended_action: str
    requires_human_review: bool
    generated_deficiency_message: str | None
    duration_ms: int
    created_at: datetime
    updated_at: datetime
    reviews: list[dict[str, Any]] = []


class SyntheticFixtureMetadata(BaseModel):
    fixture_id: str
    document_category: str
    scenario: str
    institution_name: str
    institution_identifier: str
    associated_case_id: str | None = None
    academic_year: str | None = None
    ocr_text_preview: str
    expected_classification: str
    expected_pre_scrutiny_status: str
    expected_recommended_action: str
    description: str

