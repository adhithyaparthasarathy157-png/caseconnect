from enum import StrEnum


class Role(StrEnum):
    ADMIN = "System Administrator"
    RB_OFFICER = "RB Officer"
    PGRC_OFFICER = "PGRC Officer"
    OTHER_BUREAU_OFFICER = "Other Bureau Officer"
    REGIONAL_OFFICER = "Regional Office Officer"
    SENIOR_MANAGEMENT = "Senior Management"
    COMPETENT_AUTHORITY = "Competent Authority"
    INSTITUTION_REPRESENTATIVE = "Institution Representative"


class CaseStatus(StrEnum):
    RECEIVED = "Received"
    UNDER_REVIEW = "Under Review"
    UNDER_PROCESS = "Under Process"
    PENDING_INSTITUTION_RESPONSE = "Pending Institution Response"
    TRANSFERRED = "Transferred"
    ESCALATED = "Escalated"
    DISPOSED = "Disposed"
    CLOSED = "Closed"


class Priority(StrEnum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class ActionType(StrEnum):
    CREATED = "created"
    STATUS_CHANGED = "status_changed"
    ASSIGNED = "assigned"
    REASSIGNED = "reassigned"
    TRANSFERRED = "transferred"
    ESCALATED = "escalated"
    NOTE = "note"
    UPDATED = "updated"


class OverlapStatus(StrEnum):
    PENDING = "Pending Review"
    CONFIRMED = "Confirmed Related"
    DISMISSED = "Dismissed"
    COORDINATION_REQUESTED = "Coordination Requested"


class CoordinationStatus(StrEnum):
    PENDING = "Pending Response"
    RESPONDED = "Responded"
    MORE_INFORMATION = "More Information Requested"
    RESOLVED = "Resolved"


class AlertSeverity(StrEnum):
    INFO = "Info"
    WARNING = "Warning"
    CRITICAL = "Critical"


class SlaStatus(StrEnum):
    ON_TRACK = "ON_TRACK"
    WARNING = "WARNING"
    AT_RISK = "AT_RISK"
    BREACHED = "BREACHED"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"


class SlaCalendarType(StrEnum):
    CALENDAR_DAYS = "calendar_days"
    BUSINESS_DAYS = "business_days"

