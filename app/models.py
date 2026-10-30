from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import (
    ActionType,
    AlertSeverity,
    CaseStatus,
    CoordinationStatus,
    OverlapStatus,
    Priority,
    Role,
)


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Bureau(Base, Timestamped):
    __tablename__ = "bureaus"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    region: Mapped[str | None] = mapped_column(String(80))
    users: Mapped[list["User"]] = relationship(back_populates="bureau")


class User(Base, Timestamped):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    bureau_id: Mapped[int | None] = mapped_column(ForeignKey("bureaus.id"), index=True)
    institution_id: Mapped[int | None] = mapped_column(ForeignKey("institutions.id"), index=True)
    region_scope: Mapped[str | None] = mapped_column(String(255), comment="Comma-separated regions or ALL")
    bureau: Mapped[Bureau | None] = relationship(back_populates="users")
    institution: Mapped["Institution | None"] = relationship(foreign_keys=[institution_id])


class Institution(Base, Timestamped):
    __tablename__ = "institutions"
    __table_args__ = (
        UniqueConstraint("permanent_id", name="uq_institution_permanent_id"),
        Index("ix_institutions_normalized_name", "normalized_name"),
        Index("ix_institutions_region_status", "region", "status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    permanent_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    permanent_id_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    name: Mapped[str] = mapped_column(String(255), index=True)
    normalized_name: Mapped[str] = mapped_column(String(255))
    institution_type: Mapped[str] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(String(500))
    city: Mapped[str | None] = mapped_column(String(100))
    district: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(50), default="Active", nullable=False)
    cases: Mapped[list["Case"]] = relationship(back_populates="institution")


class Case(Base, Timestamped):
    __tablename__ = "cases"
    __table_args__ = (
        Index("ix_cases_status_bureau", "status", "current_bureau_id"),
        Index("ix_cases_receipt_date", "receipt_at"),
        Index("ix_cases_receipt_date_only", "receipt_date"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    external_reference: Mapped[str | None] = mapped_column(String(120), index=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"), index=True)
    receipt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    # `receipt_at` is retained for historical compatibility. New API writes use
    # this separate date-only field; no receipt time is collected from users.
    receipt_date: Mapped[date] = mapped_column(nullable=False)
    source_channel: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(100), index=True)
    subcategory: Mapped[str | None] = mapped_column(String(100))
    subject: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    priority: Mapped[Priority] = mapped_column(Enum(Priority), default=Priority.MEDIUM, nullable=False)
    originating_bureau_id: Mapped[int] = mapped_column(ForeignKey("bureaus.id"), nullable=False, index=True)
    current_bureau_id: Mapped[int] = mapped_column(ForeignKey("bureaus.id"), nullable=False, index=True)
    assigned_officer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[CaseStatus] = mapped_column(Enum(CaseStatus), default=CaseStatus.RECEIVED, nullable=False, index=True)
    last_action: Mapped[str] = mapped_column(String(300), default="Case received", nullable=False)
    last_action_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    next_action: Mapped[str | None] = mapped_column(String(300))
    expected_disposal_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    closure_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    institution: Mapped[Institution] = relationship(back_populates="cases")
    originating_bureau: Mapped[Bureau] = relationship(foreign_keys=[originating_bureau_id])
    current_bureau: Mapped[Bureau] = relationship(foreign_keys=[current_bureau_id])
    assigned_officer: Mapped[User | None] = relationship(foreign_keys=[assigned_officer_id])
    history: Mapped[list["CaseEvent"]] = relationship(back_populates="case", cascade="all, delete-orphan", order_by="CaseEvent.created_at")


class CaseEvent(Base):
    __tablename__ = "case_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True, nullable=False)
    action_type: Mapped[ActionType] = mapped_column(Enum(ActionType), nullable=False)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    bureau_id: Mapped[int | None] = mapped_column(ForeignKey("bureaus.id"))
    previous_values: Mapped[dict | None] = mapped_column(JSON)
    new_values: Mapped[dict | None] = mapped_column(JSON)
    remarks: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    case: Mapped[Case] = relationship(back_populates="history")
    actor: Mapped[User | None] = relationship(foreign_keys=[actor_id])
    bureau: Mapped[Bureau | None] = relationship(foreign_keys=[bureau_id])


class OverlapCandidate(Base, Timestamped):
    __tablename__ = "overlap_candidates"
    __table_args__ = (UniqueConstraint("case_low_id", "case_high_id", name="uq_overlap_pair"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    case_low_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    case_high_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    similarity_score: Mapped[int] = mapped_column(nullable=False)
    identity_match: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reasons: Mapped[list] = mapped_column(JSON, nullable=False)
    status: Mapped[OverlapStatus] = mapped_column(Enum(OverlapStatus), default=OverlapStatus.PENDING, nullable=False)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    remarks: Mapped[str | None] = mapped_column(Text)
    case_low: Mapped[Case] = relationship(foreign_keys=[case_low_id])
    case_high: Mapped[Case] = relationship(foreign_keys=[case_high_id])
    reviewer: Mapped[User | None] = relationship(foreign_keys=[reviewer_id])

    @property
    def case_low_reference(self) -> str | None:
        return self.case_low.case_id if self.case_low else None

    @property
    def case_high_reference(self) -> str | None:
        return self.case_high.case_id if self.case_high else None

    @property
    def institution_name(self) -> str | None:
        return self.case_low.institution.name if self.case_low and self.case_low.institution else None

    @property
    def case_low_bureau_id(self) -> int | None:
        return self.case_low.current_bureau_id if self.case_low else None

    @property
    def case_high_bureau_id(self) -> int | None:
        return self.case_high.current_bureau_id if self.case_high else None

    @property
    def is_cross_bureau(self) -> bool:
        return bool(
            self.case_low
            and self.case_high
            and self.case_low.current_bureau_id != self.case_high.current_bureau_id
        )


class CoordinationRequest(Base, Timestamped):
    """A human-created, advisory cross-bureau request linked to an overlap."""
    __tablename__ = "coordination_requests"
    __table_args__ = (UniqueConstraint("overlap_id", name="uq_coordination_overlap"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    overlap_id: Mapped[int] = mapped_column(ForeignKey("overlap_candidates.id"), nullable=False, index=True)
    requesting_case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    receiving_case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    requesting_bureau_id: Mapped[int] = mapped_column(ForeignKey("bureaus.id"), nullable=False, index=True)
    receiving_bureau_id: Mapped[int] = mapped_column(ForeignKey("bureaus.id"), nullable=False, index=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[CoordinationStatus] = mapped_column(Enum(CoordinationStatus), default=CoordinationStatus.PENDING, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str | None] = mapped_column(Text)
    responded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    overlap: Mapped[OverlapCandidate] = relationship(foreign_keys=[overlap_id])
    requesting_case: Mapped[Case] = relationship(foreign_keys=[requesting_case_id])
    receiving_case: Mapped[Case] = relationship(foreign_keys=[receiving_case_id])
    requester: Mapped[User] = relationship(foreign_keys=[requester_id])
    responder: Mapped[User | None] = relationship(foreign_keys=[responded_by_id])


class Alert(Base, Timestamped):
    __tablename__ = "alerts"
    __table_args__ = (UniqueConstraint("dedupe_key", name="uq_alert_dedupe_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[AlertSeverity] = mapped_column(Enum(AlertSeverity), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"), index=True)
    overlap_id: Mapped[int | None] = mapped_column(ForeignKey("overlap_candidates.id"), index=True)
    bureau_id: Mapped[int | None] = mapped_column(ForeignKey("bureaus.id"), index=True)
    region: Mapped[str | None] = mapped_column(String(80), index=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    case: Mapped[Case | None] = relationship(foreign_keys=[case_id])

    @property
    def case_reference(self) -> str | None:
        return self.case.case_id if self.case else None


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[str] = mapped_column(String(80), index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    details: Mapped[dict | None] = mapped_column(JSON)
    remarks: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DocumentAnalysis(Base, Timestamped):
    __tablename__ = "document_analyses"
    __table_args__ = (
        Index("ix_doc_analyses_case_id", "case_numeric_id"),
        Index("ix_doc_analyses_institution_id", "institution_id"),
        Index("ix_doc_analyses_status", "pre_scrutiny_status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    case_numeric_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    case_id: Mapped[str] = mapped_column(String(40), index=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"), index=True)
    document_type: Mapped[str] = mapped_column(String(100), index=True)
    input_source: Mapped[str] = mapped_column(String(50), default="manual_ocr")
    fixture_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ocr_text: Mapped[str] = mapped_column(Text)
    ocr_text_snippet: Mapped[str] = mapped_column(String(500))
    extracted_fields: Mapped[dict] = mapped_column(JSON, default=dict)
    field_evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    findings: Mapped[list] = mapped_column(JSON, default=list)
    classification_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    top_alternatives: Mapped[list] = mapped_column(JSON, default=list)
    classification_method: Mapped[str] = mapped_column(String(100))
    model_name: Mapped[str] = mapped_column(String(100))
    analysis_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    parent_analysis_id: Mapped[int | None] = mapped_column(ForeignKey("document_analyses.id"), nullable=True)
    pre_scrutiny_status: Mapped[str] = mapped_column(String(50), index=True)
    recommended_action: Mapped[str] = mapped_column(String(500))
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=False)
    generated_deficiency_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    case: Mapped[Case] = relationship(foreign_keys=[case_numeric_id])
    institution: Mapped[Institution] = relationship(foreign_keys=[institution_id])
    parent_analysis: Mapped["DocumentAnalysis | None"] = relationship(remote_side=[id], backref="child_analyses")
    reviews: Mapped[list["DocumentAnalysisReview"]] = relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
        order_by="DocumentAnalysisReview.created_at",
    )


class DocumentAnalysisReview(Base, Timestamped):
    __tablename__ = "document_analysis_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("document_analyses.id"), index=True)
    reviewer_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    review_action: Mapped[str] = mapped_column(String(50))  # "confirm", "dismiss_finding", "edit_finding", "manual_verify", "approve_correction"
    reviewer_comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    finding_updates: Mapped[list] = mapped_column(JSON, default=list)
    final_review_status: Mapped[str | None] = mapped_column(String(50), nullable=True)

    analysis: Mapped[DocumentAnalysis] = relationship(back_populates="reviews")
    reviewer: Mapped[User | None] = relationship(foreign_keys=[reviewer_user_id])



class ComplaintSubmission(Base, Timestamped):
    """
    Complaint submission from institution representative, screened BEFORE case registration.
    Stays separate from cases until screening PASSES and admin registers the case.
    """
    __tablename__ = "complaint_submissions"
    __table_args__ = (
        Index("ix_submissions_institution_id", "institution_id"),
        Index("ix_submissions_status", "screening_status"),
        Index("ix_submissions_permanent_id", "permanent_id_submitted"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    submission_ref: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    institution_id: Mapped[int | None] = mapped_column(ForeignKey("institutions.id"), nullable=True, index=True)
    permanent_id_submitted: Mapped[str | None] = mapped_column(String(64), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(300), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    incident_date: Mapped[str | None] = mapped_column(String(30), nullable=True)
    contact_info: Mapped[str | None] = mapped_column(String(255), nullable=True)
    previous_complaint_ref: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # Screening state
    screening_status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)
    screening_outcome: Mapped[str | None] = mapped_column(String(50), nullable=True)
    screening_outcome_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    admin_override: Mapped[str | None] = mapped_column(String(50), nullable=True)
    admin_override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_override_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    admin_override_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Resubmission tracking
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    parent_submission_id: Mapped[int | None] = mapped_column(ForeignKey("complaint_submissions.id"), nullable=True)
    # Source
    submitted_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    is_synthetic_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    demo_scenario_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    expected_demo_outcome: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Case registration (if screening passes and admin registers)
    registered_case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"), nullable=True)

    institution: Mapped["Institution | None"] = relationship(foreign_keys=[institution_id])
    submitted_by: Mapped["User | None"] = relationship(foreign_keys=[submitted_by_id])
    admin_override_user: Mapped["User | None"] = relationship(foreign_keys=[admin_override_by_id])
    registered_case: Mapped["Case | None"] = relationship(foreign_keys=[registered_case_id])
    parent_submission: Mapped["ComplaintSubmission | None"] = relationship(
        remote_side=[id], foreign_keys=[parent_submission_id], backref="resubmissions"
    )
