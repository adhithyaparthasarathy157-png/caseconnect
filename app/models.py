from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
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
    region_scope: Mapped[str | None] = mapped_column(String(255), comment="Comma-separated regions or ALL")
    bureau: Mapped[Bureau | None] = relationship(back_populates="users")


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
    __table_args__ = (Index("ix_cases_status_bureau", "status", "current_bureau_id"), Index("ix_cases_receipt_date", "receipt_at"))
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    external_reference: Mapped[str | None] = mapped_column(String(120), index=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"), index=True)
    receipt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
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
