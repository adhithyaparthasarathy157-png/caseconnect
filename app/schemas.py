from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from pydantic_core import PydanticCustomError

from app.enums import (
    ActionType,
    AlertSeverity,
    CaseStatus,
    CoordinationStatus,
    OverlapStatus,
    Priority,
    Role,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class UserPublic(ORMModel):
    id: int
    email: EmailStr
    full_name: str
    role: Role
    is_active: bool
    bureau_id: int | None
    institution_id: int | None
    region_scope: str | None


class BureauPublic(ORMModel):
    id: int
    code: str
    name: str
    region: str | None


class InstitutionBase(BaseModel):
    permanent_id: str | None = Field(default=None, max_length=64)
    permanent_id_verified: bool = False
    name: str = Field(min_length=2, max_length=255)
    institution_type: str = Field(min_length=2, max_length=100)
    address: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    region: str = Field(min_length=2, max_length=80)
    status: str = Field(default="Active", max_length=50)

    @field_validator("permanent_id")
    @classmethod
    def normalize_permanent_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split()).upper()
        return normalized or None

    @field_validator("name", "region", "institution_type")
    @classmethod
    def trim_required_institution_text(cls, value: str) -> str:
        return " ".join(value.split())


class InstitutionCreate(InstitutionBase):
    pass


class InstitutionUpdate(BaseModel):
    permanent_id: str | None = Field(default=None, max_length=64)
    permanent_id_verified: bool | None = None
    name: str | None = Field(default=None, min_length=2, max_length=255)
    institution_type: str | None = Field(default=None, min_length=2, max_length=100)
    address: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, min_length=2, max_length=80)
    status: str | None = Field(default=None, max_length=50)

    @field_validator("permanent_id")
    @classmethod
    def normalize_permanent_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split()).upper()
        return normalized or None

    @field_validator("name", "region", "institution_type")
    @classmethod
    def trim_optional_institution_text(cls, value: str | None) -> str | None:
        return " ".join(value.split()) if value else value


class InstitutionPublic(InstitutionBase, ORMModel):
    id: int
    normalized_name: str
    created_at: datetime
    updated_at: datetime


class InstitutionRelatedOverlap(BaseModel):
    id: int
    case_id: str
    related_case_id: str
    similarity_score: int
    status: OverlapStatus
    reasons: list


class InstitutionRelatedCoordination(BaseModel):
    """A coordination record whose two cases are both visible in a profile."""
    id: str
    overlap_id: int
    requesting_case_id: int
    receiving_case_id: int
    status: CoordinationStatus
    reason: str
    response: str | None
    responded_at: datetime | None
    updated_at: datetime


class InstitutionProfile(InstitutionPublic):
    total_cases: int
    cases_by_status: dict[str, int]
    cases: list["CasePublic"]
    related_overlaps: list[InstitutionRelatedOverlap]
    related_coordination: list[InstitutionRelatedCoordination]
    accounts: list[UserPublic] = []


class CaseCreate(BaseModel):
    external_reference: str | None = Field(default=None, max_length=120)
    institution_id: int | None = None
    receipt_date: date
    source_channel: str = Field(min_length=2, max_length=100)
    category: str = Field(min_length=2, max_length=100)
    subcategory: str | None = Field(default=None, max_length=100)
    subject: str = Field(min_length=4, max_length=300)
    description: str
    priority: Priority = Priority.MEDIUM
    originating_bureau_id: int | None = None
    current_bureau_id: int | None = None
    assigned_officer_id: int | None = None
    next_action: str | None = Field(default=None, max_length=300)
    expected_disposal_date: datetime | None = None

    @field_validator("description")
    @classmethod
    def description_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise PydanticCustomError("description_blank", "Description is required")
        return value


class CaseUpdate(BaseModel):
    category: str | None = Field(default=None, min_length=2, max_length=100)
    subcategory: str | None = Field(default=None, max_length=100)
    subject: str | None = Field(default=None, min_length=4, max_length=300)
    description: str | None = None
    priority: Priority | None = None
    status: CaseStatus | None = None
    assigned_officer_id: int | None = None
    next_action: str | None = Field(default=None, max_length=300)
    expected_disposal_date: datetime | None = None
    remarks: str | None = Field(default=None, max_length=2000)

    @field_validator("description")
    @classmethod
    def description_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise PydanticCustomError("description_blank", "Description is required")
        return value


class CaseActionCreate(BaseModel):
    action_type: ActionType
    target_bureau_id: int | None = None
    assigned_officer_id: int | None = None
    status: CaseStatus | None = None
    remarks: str = Field(min_length=2, max_length=2000)


class CasePublic(ORMModel):
    id: int
    case_id: str
    external_reference: str | None
    institution_id: int
    receipt_date: date
    source_channel: str
    category: str
    subcategory: str | None
    subject: str
    description: str
    priority: Priority
    originating_bureau_id: int
    current_bureau_id: int
    assigned_officer_id: int | None
    status: CaseStatus
    last_action: str
    last_action_at: datetime
    next_action: str | None
    expected_disposal_date: datetime | None
    closure_date: datetime | None
    created_at: datetime
    updated_at: datetime


class CaseEventPublic(ORMModel):
    id: str
    case_id: int
    action_type: ActionType
    actor_id: int | None
    bureau_id: int | None
    previous_values: dict | None
    new_values: dict | None
    remarks: str | None
    created_at: datetime


InstitutionProfile.model_rebuild()


class PaginatedCases(BaseModel):
    items: list[CasePublic]
    total: int
    page: int
    page_size: int


class OverlapPublic(ORMModel):
    id: int
    case_low_id: int
    case_high_id: int
    case_low_reference: str | None
    case_high_reference: str | None
    case_low_bureau_id: int | None = None
    case_high_bureau_id: int | None = None
    is_cross_bureau: bool = False
    institution_name: str | None
    similarity_score: int
    identity_match: bool
    reasons: list
    status: OverlapStatus
    reviewer_id: int | None
    reviewed_at: datetime | None
    remarks: str | None
    created_at: datetime
    updated_at: datetime


class OverlapReview(BaseModel):
    status: OverlapStatus
    remarks: str = Field(min_length=2, max_length=2000)


class CoordinationCreate(BaseModel):
    requesting_case_id: int
    reason: str = Field(min_length=2, max_length=2000)


class CoordinationResponse(BaseModel):
    status: CoordinationStatus
    response: str = Field(min_length=2, max_length=2000)


class CoordinationPublic(ORMModel):
    id: str
    overlap_id: int
    requesting_case_id: int
    receiving_case_id: int
    requesting_bureau_id: int
    receiving_bureau_id: int
    requester_id: int
    status: CoordinationStatus
    reason: str
    response: str | None
    responded_by_id: int | None
    responded_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AlertPublic(ORMModel):
    id: str
    alert_type: str
    severity: AlertSeverity
    title: str
    message: str
    case_id: int | None
    case_reference: str | None = None
    overlap_id: int | None
    bureau_id: int | None
    region: str | None
    is_read: bool
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime


class AuditEventPublic(ORMModel):
    id: str
    entity_type: str
    entity_id: str
    action: str
    actor_id: int | None
    details: dict | None
    remarks: str | None
    created_at: datetime


class CaseContext(BaseModel):
    case: CasePublic
    history: list[CaseEventPublic]
    overlaps: list[OverlapPublic]
    alerts: list[AlertPublic]
    coordination: list[CoordinationPublic]
