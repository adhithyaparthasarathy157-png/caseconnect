"""Declarative Pre-Scrutiny Requirements Registry for AICTE Documents.

Defines mandatory fields, validation rules, regulatory constraints, and severity levels
for each supported document category.
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel

from app.document_intelligence.schemas import (
    DocumentCategory,
    FindingSeverity,
    FindingType,
)


class FieldRequirement(BaseModel):
    field_name: str
    display_name: str
    is_mandatory: bool
    missing_severity: FindingSeverity = FindingSeverity.CRITICAL
    description: str


class CategoryRequirements(BaseModel):
    category: DocumentCategory
    title: str
    description: str
    mandatory_fields: list[FieldRequirement]
    optional_fields: list[FieldRequirement] = []
    requires_institution_match: bool = True
    requires_validity_check: bool = True
    requires_signatory_check: bool = True


# Requirements definition across the 5 mandatory categories
REQUIREMENTS_REGISTRY: dict[DocumentCategory, CategoryRequirements] = {
    DocumentCategory.AFFILIATION_CERTIFICATE: CategoryRequirements(
        category=DocumentCategory.AFFILIATION_CERTIFICATE,
        title="University Affiliation Certificate",
        description="Official certificate/order issued by affiliating State/Central University granting affiliation.",
        mandatory_fields=[
            FieldRequirement(
                field_name="issuing_authority",
                display_name="Affiliating University / Authority",
                is_mandatory=True,
                missing_severity=FindingSeverity.CRITICAL,
                description="Recognized affiliating university or state board name.",
            ),
            FieldRequirement(
                field_name="institution_name",
                display_name="Institution Name",
                is_mandatory=True,
                missing_severity=FindingSeverity.CRITICAL,
                description="Full legal name of the affiliated college or institute.",
            ),
            FieldRequirement(
                field_name="academic_year",
                display_name="Academic Year",
                is_mandatory=True,
                missing_severity=FindingSeverity.CRITICAL,
                description="Academic session for which affiliation is granted (e.g. 2024-25).",
            ),
            FieldRequirement(
                field_name="authorized_signatory",
                display_name="Authorized Signatory",
                is_mandatory=True,
                missing_severity=FindingSeverity.WARNING,
                description="Registrar or authorized officer signature/designation.",
            ),
        ],
        optional_fields=[
            FieldRequirement(
                field_name="institution_code",
                display_name="Institution / College Code",
                is_mandatory=False,
                missing_severity=FindingSeverity.INFO,
                description="University assigned institution code.",
            ),
            FieldRequirement(
                field_name="valid_till_date",
                display_name="Validity Period / Date",
                is_mandatory=False,
                missing_severity=FindingSeverity.WARNING,
                description="Expiry date or validity duration of provisional affiliation.",
            ),
            FieldRequirement(
                field_name="approved_intake",
                display_name="Sanctioned Intake",
                is_mandatory=False,
                missing_severity=FindingSeverity.INFO,
                description="Total approved seats across affiliated courses.",
            ),
            FieldRequirement(
                field_name="affiliation_type",
                display_name="Affiliation Type",
                is_mandatory=False,
                missing_severity=FindingSeverity.INFO,
                description="Provisional or Permanent affiliation status.",
            ),
        ],
        requires_institution_match=True,
        requires_validity_check=True,
        requires_signatory_check=True,
    ),
    DocumentCategory.APPROVAL_LETTER: CategoryRequirements(
        category=DocumentCategory.APPROVAL_LETTER,
        title="AICTE Extension of Approval (EOA) Letter",
        description="Formal AICTE council order granting Extension of Approval or Letter of Approval.",
        mandatory_fields=[
            FieldRequirement(
                field_name="approval_reference_number",
                display_name="Approval Reference Number",
                is_mandatory=True,
                missing_severity=FindingSeverity.CRITICAL,
                description="Official AICTE dispatch / file reference number.",
            ),
            FieldRequirement(
                field_name="institution_name",
                display_name="Institution Name",
                is_mandatory=True,
                missing_severity=FindingSeverity.CRITICAL,
                description="Approved technical institute name.",
            ),
            FieldRequirement(
                field_name="institution_id",
                display_name="AICTE Permanent Institute ID",
                is_mandatory=True,
                missing_severity=FindingSeverity.CRITICAL,
                description="Permanent Institute ID assigned on the AICTE web portal.",
            ),
            FieldRequirement(
                field_name="academic_year",
                display_name="Academic Year",
                is_mandatory=True,
                missing_severity=FindingSeverity.CRITICAL,
                description="Academic year approved for operation (e.g. 2024-25).",
            ),
            FieldRequirement(
                field_name="signatory",
                display_name="Competent Signatory",
                is_mandatory=True,
                missing_severity=FindingSeverity.WARNING,
                description="Member Secretary or AICTE Regional Officer designation.",
            ),
        ],
        optional_fields=[
            FieldRequirement(
                field_name="approved_intake",
                display_name="Approved Total Intake",
                is_mandatory=False,
                missing_severity=FindingSeverity.INFO,
                description="Total approved student intake capacity.",
            ),
            FieldRequirement(
                field_name="affiliating_university",
                display_name="Affiliating University",
                is_mandatory=False,
                missing_severity=FindingSeverity.INFO,
                description="Stated affiliating university body.",
            ),
        ],
        requires_institution_match=True,
        requires_validity_check=True,
        requires_signatory_check=True,
    ),
    DocumentCategory.INSTITUTION_REGISTRATION: CategoryRequirements(
        category=DocumentCategory.INSTITUTION_REGISTRATION,
        title="Institution Registration Certificate (Society / Trust)",
        description="Government Certificate of Registration under Societies Registration Act or Indian Trusts Act.",
        mandatory_fields=[
            FieldRequirement(
                field_name="trust_or_society_name",
                display_name="Society / Trust Name",
                is_mandatory=True,
                missing_severity=FindingSeverity.CRITICAL,
                description="Sponsoring trust or educational society legal title.",
            ),
            FieldRequirement(
                field_name="registration_number",
                display_name="Registration Number",
                is_mandatory=True,
                missing_severity=FindingSeverity.CRITICAL,
                description="Official registered serial number assigned by Registrar.",
            ),
            FieldRequirement(
                field_name="registration_act",
                display_name="Governing Act",
                is_mandatory=True,
                missing_severity=FindingSeverity.CRITICAL,
                description="Statutory Act (e.g. Societies Registration Act, 1860).",
            ),
            FieldRequirement(
                field_name="issuing_authority",
                display_name="Issuing Authority / Registrar",
                is_mandatory=True,
                missing_severity=FindingSeverity.WARNING,
                description="Office of Registrar of Societies / Charity Commissioner.",
            ),
        ],
        optional_fields=[
            FieldRequirement(
                field_name="registration_date",
                display_name="Registration Date",
                is_mandatory=False,
                missing_severity=FindingSeverity.INFO,
                description="Date of incorporation / registration.",
            ),
            FieldRequirement(
                field_name="registered_address",
                display_name="Registered Office Address",
                is_mandatory=False,
                missing_severity=FindingSeverity.INFO,
                description="Official registered office location.",
            ),
        ],
        requires_institution_match=False,  # Registration certificate is in the name of the Trust/Society
        requires_validity_check=False,
        requires_signatory_check=True,
    ),
    DocumentCategory.FACULTY_STATEMENT: CategoryRequirements(
        category=DocumentCategory.FACULTY_STATEMENT,
        title="Faculty Details Statement",
        description="Certified teaching faculty statement detailing cadre composition and SFR compliance.",
        mandatory_fields=[
            FieldRequirement(
                field_name="institution_name",
                display_name="Institution Name",
                is_mandatory=True,
                missing_severity=FindingSeverity.CRITICAL,
                description="Name of the institution submitting the roster.",
            ),
            FieldRequirement(
                field_name="academic_year",
                display_name="Academic Year",
                is_mandatory=True,
                missing_severity=FindingSeverity.CRITICAL,
                description="Academic session of the faculty roster.",
            ),
            FieldRequirement(
                field_name="total_faculty_count",
                display_name="Total Teaching Faculty Count",
                is_mandatory=True,
                missing_severity=FindingSeverity.CRITICAL,
                description="Total number of regular teaching faculty members.",
            ),
            FieldRequirement(
                field_name="student_faculty_ratio",
                display_name="Student to Faculty Ratio (SFR)",
                is_mandatory=True,
                missing_severity=FindingSeverity.CRITICAL,
                description="Overall institution or department SFR (AICTE norm: <= 1:20 for Engineering/Tech).",
            ),
            FieldRequirement(
                field_name="certifying_authority",
                display_name="Principal / HoD Signature",
                is_mandatory=True,
                missing_severity=FindingSeverity.WARNING,
                description="Certification by Head of Institution.",
            ),
        ],
        optional_fields=[
            FieldRequirement(
                field_name="professors_count",
                display_name="Professors Count",
                is_mandatory=False,
                missing_severity=FindingSeverity.INFO,
                description="Number of full Professors.",
            ),
            FieldRequirement(
                field_name="associate_professors_count",
                display_name="Associate Professors Count",
                is_mandatory=False,
                missing_severity=FindingSeverity.INFO,
                description="Number of Associate Professors.",
            ),
            FieldRequirement(
                field_name="assistant_professors_count",
                display_name="Assistant Professors Count",
                is_mandatory=False,
                missing_severity=FindingSeverity.INFO,
                description="Number of Assistant Professors.",
            ),
            FieldRequirement(
                field_name="cadre_ratio",
                display_name="Cadre Ratio (1:2:6)",
                is_mandatory=False,
                missing_severity=FindingSeverity.WARNING,
                description="Distribution of Professor : Associate Professor : Assistant Professor.",
            ),
        ],
        requires_institution_match=True,
        requires_validity_check=True,
        requires_signatory_check=True,
    ),
    DocumentCategory.INFRASTRUCTURE_REPORT: CategoryRequirements(
        category=DocumentCategory.INFRASTRUCTURE_REPORT,
        title="Infrastructure and Physical Facilities Report",
        description="Architect/Engineer certified report on land, built-up area, classrooms, and fire safety.",
        mandatory_fields=[
            FieldRequirement(
                field_name="institution_name",
                display_name="Institution Name",
                is_mandatory=True,
                missing_severity=FindingSeverity.CRITICAL,
                description="Institution name as per land and building title.",
            ),
            FieldRequirement(
                field_name="land_area_acres",
                display_name="Total Land Area",
                is_mandatory=True,
                missing_severity=FindingSeverity.CRITICAL,
                description="Contiguous land area in acres (AICTE norm: minimum 2.5 to 5.0 acres depending on terrain).",
            ),
            FieldRequirement(
                field_name="total_built_up_area_sqm",
                display_name="Total Built-up Area",
                is_mandatory=True,
                missing_severity=FindingSeverity.CRITICAL,
                description="Overall certified built-up area in square meters.",
            ),
            FieldRequirement(
                field_name="instructional_area_sqm",
                display_name="Instructional Area",
                is_mandatory=True,
                missing_severity=FindingSeverity.WARNING,
                description="Area allocated for classrooms, tutorial rooms, laboratories, and drawing halls.",
            ),
            FieldRequirement(
                field_name="fire_safety_certificate",
                display_name="Fire Safety NOC / Certificate",
                is_mandatory=True,
                missing_severity=FindingSeverity.CRITICAL,
                description="Valid fire safety compliance clearance from Fire Services Department.",
            ),
        ],
        optional_fields=[
            FieldRequirement(
                field_name="administrative_area_sqm",
                display_name="Administrative Area",
                is_mandatory=False,
                missing_severity=FindingSeverity.INFO,
                description="Area for principal office, administrative offices, and staff rooms.",
            ),
            FieldRequirement(
                field_name="amenities_area_sqm",
                display_name="Amenities Area",
                is_mandatory=False,
                missing_severity=FindingSeverity.INFO,
                description="Cafeteria, sports rooms, and common amenities.",
            ),
            FieldRequirement(
                field_name="classrooms_count",
                display_name="Classrooms Count",
                is_mandatory=False,
                missing_severity=FindingSeverity.INFO,
                description="Total number of dedicated classrooms.",
            ),
            FieldRequirement(
                field_name="laboratories_count",
                display_name="Laboratories Count",
                is_mandatory=False,
                missing_severity=FindingSeverity.INFO,
                description="Total number of functional specialized laboratories.",
            ),
            FieldRequirement(
                field_name="certifying_engineer",
                display_name="Chartered Engineer / Architect",
                is_mandatory=False,
                missing_severity=FindingSeverity.WARNING,
                description="Professional architect or civil engineer certification.",
            ),
        ],
        requires_institution_match=True,
        requires_validity_check=False,
        requires_signatory_check=True,
    ),
    DocumentCategory.FEE_RECEIPT_PAYMENT: CategoryRequirements(
        category=DocumentCategory.FEE_RECEIPT_PAYMENT,
        title="Fee Receipt & Payment Evidence",
        description="Official payment receipt, counterfoil, or bank transaction proof supporting financial complaints.",
        mandatory_fields=[
            FieldRequirement(
                field_name="institution_name",
                display_name="Institution Name",
                is_mandatory=True,
                missing_severity=FindingSeverity.CRITICAL,
                description="Institution to which payment was made.",
            ),
            FieldRequirement(
                field_name="receipt_number",
                display_name="Receipt / Transaction Reference",
                is_mandatory=True,
                missing_severity=FindingSeverity.CRITICAL,
                description="Unique receipt number or bank transaction reference ID.",
            ),
            FieldRequirement(
                field_name="amount",
                display_name="Payment Amount",
                is_mandatory=True,
                missing_severity=FindingSeverity.CRITICAL,
                description="Paid or deposited monetary amount (e.g. caution money, tuition).",
            ),
            FieldRequirement(
                field_name="payment_date",
                display_name="Payment / Transaction Date",
                is_mandatory=True,
                missing_severity=FindingSeverity.WARNING,
                description="Date on which payment was deposited or receipt was issued.",
            ),
        ],
        optional_fields=[
            FieldRequirement(
                field_name="student_name",
                display_name="Student / Payer Name",
                is_mandatory=False,
                missing_severity=FindingSeverity.INFO,
                description="Name of the student or remitter.",
            ),
            FieldRequirement(
                field_name="fee_type",
                display_name="Fee Head / Purpose",
                is_mandatory=False,
                missing_severity=FindingSeverity.INFO,
                description="Fee head (e.g., Caution Deposit, Development Fee, Tuition).",
            ),
        ],
        requires_institution_match=True,
        requires_validity_check=False,
        requires_signatory_check=False,
    ),
    DocumentCategory.COMPLAINT_LETTER: CategoryRequirements(
        category=DocumentCategory.COMPLAINT_LETTER,
        title="Formal Complaint / Grievance Petition",
        description="Signed complaint representation or formal grievance submitted by complainant.",
        mandatory_fields=[
            FieldRequirement(
                field_name="institution_name",
                display_name="Institution Name",
                is_mandatory=True,
                missing_severity=FindingSeverity.CRITICAL,
                description="Institution against which grievance is raised.",
            ),
            FieldRequirement(
                field_name="complainant_name",
                display_name="Complainant Name",
                is_mandatory=True,
                missing_severity=FindingSeverity.CRITICAL,
                description="Full legal name of the petitioning complainant or representative.",
            ),
            FieldRequirement(
                field_name="complaint_date",
                display_name="Complaint / Representation Date",
                is_mandatory=True,
                missing_severity=FindingSeverity.WARNING,
                description="Date of the formal representation or grievance petition.",
            ),
        ],
        optional_fields=[
            FieldRequirement(
                field_name="subject",
                display_name="Grievance Subject",
                is_mandatory=False,
                missing_severity=FindingSeverity.INFO,
                description="Subject or heading of the complaint.",
            ),
        ],
        requires_institution_match=True,
        requires_validity_check=False,
        requires_signatory_check=False,
    ),
    DocumentCategory.INSTITUTIONAL_NOTICE: CategoryRequirements(
        category=DocumentCategory.INSTITUTIONAL_NOTICE,
        title="Institutional Notice & Circular",
        description="Official circular or directive issued by the institution management or principal.",
        mandatory_fields=[
            FieldRequirement(
                field_name="institution_name",
                display_name="Issuing Institution",
                is_mandatory=True,
                missing_severity=FindingSeverity.CRITICAL,
                description="College or institute issuing the circular.",
            ),
            FieldRequirement(
                field_name="notice_date",
                display_name="Notice Date",
                is_mandatory=True,
                missing_severity=FindingSeverity.WARNING,
                description="Date of circular or official order.",
            ),
        ],
        optional_fields=[
            FieldRequirement(
                field_name="notice_reference",
                display_name="Circular / Ref Number",
                is_mandatory=False,
                missing_severity=FindingSeverity.INFO,
                description="Official memorandum or circular reference number.",
            ),
        ],
        requires_institution_match=True,
        requires_validity_check=False,
        requires_signatory_check=False,
    ),
    DocumentCategory.APPOINTMENT_TERMINATION: CategoryRequirements(
        category=DocumentCategory.APPOINTMENT_TERMINATION,
        title="Appointment / Termination Order",
        description="Official employment order, service agreement, or termination notice.",
        mandatory_fields=[
            FieldRequirement(
                field_name="institution_name",
                display_name="Institution Name",
                is_mandatory=True,
                missing_severity=FindingSeverity.CRITICAL,
                description="Employing technical institution.",
            ),
            FieldRequirement(
                field_name="employee_name",
                display_name="Employee / Faculty Name",
                is_mandatory=True,
                missing_severity=FindingSeverity.CRITICAL,
                description="Name of the affected faculty or staff member.",
            ),
            FieldRequirement(
                field_name="order_date",
                display_name="Order Date",
                is_mandatory=True,
                missing_severity=FindingSeverity.WARNING,
                description="Date of issuance of the appointment or relieving order.",
            ),
        ],
        optional_fields=[
            FieldRequirement(
                field_name="designation",
                display_name="Cadre / Designation",
                is_mandatory=False,
                missing_severity=FindingSeverity.INFO,
                description="Designation or academic department.",
            ),
        ],
        requires_institution_match=True,
        requires_validity_check=False,
        requires_signatory_check=False,
    ),
    DocumentCategory.FACULTY_EVIDENCE: CategoryRequirements(
        category=DocumentCategory.FACULTY_EVIDENCE,
        title="Faculty Complaint Evidence / Salary Record",
        description="Proof of delayed salary, bank statement, or qualification grievance.",
        mandatory_fields=[
            FieldRequirement(
                field_name="institution_name",
                display_name="Institution Name",
                is_mandatory=True,
                missing_severity=FindingSeverity.CRITICAL,
                description="Technical institution name.",
            ),
            FieldRequirement(
                field_name="faculty_name",
                display_name="Faculty Name",
                is_mandatory=True,
                missing_severity=FindingSeverity.CRITICAL,
                description="Affected faculty member.",
            ),
        ],
        optional_fields=[],
        requires_institution_match=True,
        requires_validity_check=False,
        requires_signatory_check=False,
    ),
    DocumentCategory.CORRESPONDENCE_PROOF: CategoryRequirements(
        category=DocumentCategory.CORRESPONDENCE_PROOF,
        title="Correspondence / Representation Proof",
        description="Speed post receipt, courier slip, or acknowledged communication thread.",
        mandatory_fields=[
            FieldRequirement(
                field_name="institution_name",
                display_name="Institution Name",
                is_mandatory=True,
                missing_severity=FindingSeverity.CRITICAL,
                description="Addressed or issuing institution.",
            ),
        ],
        optional_fields=[],
        requires_institution_match=True,
        requires_validity_check=False,
        requires_signatory_check=False,
    ),
}


def get_requirements_for_category(category: DocumentCategory) -> CategoryRequirements | None:
    """Retrieves pre-scrutiny criteria for the given category."""
    return REQUIREMENTS_REGISTRY.get(category)
