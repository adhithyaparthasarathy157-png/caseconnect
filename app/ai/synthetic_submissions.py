"""
Synthetic complaint submissions and document fixtures for AI Screening and Document Intelligence.
Includes:
- 10 Form-level screening test scenarios
- 8 Uploaded-document screening test scenarios
Labeled as SYNTHETIC DEMONSTRATION MATERIAL — not real complaints.
"""
from __future__ import annotations

from typing import Any

_VALID_PID_PLACEHOLDER = "__FIRST_VALID_PID__"
_VALID_PID_2_PLACEHOLDER = "__SECOND_VALID_PID__"

SYNTHETIC_SUBMISSIONS: list[dict[str, Any]] = [
    # 1. Fully valid submission — should PASS
    {
        "demo_id": "SYNTH-001",
        "scenario_name": "Valid Submission — All Criteria Passed",
        "expected_outcome": "PASSED",
        "permanent_id": _VALID_PID_PLACEHOLDER,
        "subject": "Delay in refund of caution money collected at admission",
        "description": (
            "The institution collected a caution money deposit of Rs 15,000 at the time of admission in August 2025. "
            "As per AICTE guidelines, this amount is refundable upon request after course completion or withdrawal. "
            "The student submitted a refund application on 15 September 2025, with all required supporting documents. "
            "Despite multiple follow-ups with the administration office on 01 October and 15 October 2025, "
            "no refund has been issued. The institution has not provided any written communication explaining the delay. "
            "This constitutes a violation of financial norms applicable to AICTE-approved institutions."
        ),
        "category": "Financial",
        "incident_date": "2025-09-15",
        "contact_info": "complainant@example.com",
    },
    # 2. Missing Permanent ID — should REJECT_AT_INTAKE
    {
        "demo_id": "SYNTH-002",
        "scenario_name": "Missing Institution Permanent ID",
        "expected_outcome": "REJECTED_AT_INTAKE",
        "permanent_id": "",
        "subject": "Unqualified faculty teaching core engineering subjects",
        "description": (
            "Several faculty members at the institution are teaching core engineering subjects without possessing "
            "the required qualifications as prescribed under AICTE norms. Students are being deprived of quality "
            "education as a result of this non-compliance, which has persisted for at least two academic years."
        ),
        "category": "Faculty",
        "incident_date": "2025-08-01",
        "contact_info": "student.rep@example.com",
    },
    # 3. Description too short — should be CORRECTION_REQUIRED
    {
        "demo_id": "SYNTH-003",
        "scenario_name": "Insufficient Complaint Description",
        "expected_outcome": "CORRECTION_REQUIRED",
        "permanent_id": _VALID_PID_PLACEHOLDER,
        "subject": "Poor laboratory infrastructure at the college",
        "description": "Labs are bad. Equipment broken. No computers.",
        "category": "Infrastructure",
        "incident_date": "2025-10-01",
        "contact_info": "anonymous@example.com",
    },
    # 4. Missing category — should REJECT_AT_INTAKE
    {
        "demo_id": "SYNTH-004",
        "scenario_name": "Missing Complaint Category",
        "expected_outcome": "REJECTED_AT_INTAKE",
        "permanent_id": _VALID_PID_PLACEHOLDER,
        "subject": "Irregularities in conduct of university examinations",
        "description": (
            "The institution conducted its end-semester examinations in December 2025 without following prescribed "
            "guidelines. Answer sheets were not distributed timely, supervisors were absent for extended periods, "
            "and the seating arrangement allowed widespread copying. Multiple students have submitted affidavits "
            "attesting to these irregularities. The examination registrar has not responded to student representations."
        ),
        "category": "",
        "incident_date": "2025-12-10",
    },
    # 5. Invalid category value — should REJECT_AT_INTAKE
    {
        "demo_id": "SYNTH-005",
        "scenario_name": "Invalid Category Value",
        "expected_outcome": "REJECTED_AT_INTAKE",
        "permanent_id": _VALID_PID_PLACEHOLDER,
        "subject": "Miscellaneous complaint about college activities",
        "description": (
            "The institution has not followed several AICTE directives issued during the current academic year. "
            "This includes failure to submit mandatory returns, non-compliance with student grievance redressal "
            "mechanisms, and delay in updating institution profile on AICTE portal despite multiple reminders."
        ),
        "category": "GeneralMiscellaneous",
        "incident_date": "2025-11-01",
    },
    # 6. Future incident date — should REJECT_AT_INTAKE
    {
        "demo_id": "SYNTH-006",
        "scenario_name": "Future Incident Date",
        "expected_outcome": "REJECTED_AT_INTAKE",
        "permanent_id": _VALID_PID_PLACEHOLDER,
        "subject": "Anticipated non-compliance in upcoming admission process",
        "description": (
            "The institution has informally communicated to prospective students that it plans to charge fees "
            "beyond prescribed limits during the upcoming 2026-27 admission cycle starting January 2027. "
            "Students who attended an information session on campus have reported this. "
            "Preventive regulatory action is requested before admissions commence."
        ),
        "category": "Admission",
        "incident_date": "2027-01-15",
    },
    # 7. Institution Permanent ID not in registry — should REJECT_AT_INTAKE
    {
        "demo_id": "SYNTH-007",
        "scenario_name": "Institution Not Found in Registry",
        "expected_outcome": "REJECTED_AT_INTAKE",
        "permanent_id": "1-XXXXXXXXXX",
        "subject": "Faculty recruitment irregularities at the institution",
        "description": (
            "The institution has been recruiting faculty without following the selection procedures mandated by AICTE. "
            "Internal communications obtained by former faculty members indicate that appointments were made "
            "based on personal connections rather than merit. The selection committee was not formed as required, "
            "and no external expert was included in the interview panel. At least 12 irregular appointments "
            "have been made in the last academic year alone."
        ),
        "category": "Faculty",
        "incident_date": "2025-07-01",
    },
    # 8. Subject too short — CORRECTION_REQUIRED
    {
        "demo_id": "SYNTH-008",
        "scenario_name": "Subject Too Short",
        "expected_outcome": "CORRECTION_REQUIRED",
        "permanent_id": _VALID_PID_PLACEHOLDER,
        "subject": "Bad",
        "description": (
            "The institution has consistently failed to maintain attendance records for the academic year 2025-26. "
            "Students with attendance below 75% have been allowed to appear in semester examinations, contrary "
            "to AICTE attendance regulations. This has been confirmed by multiple students who were issued hall "
            "tickets despite low attendance percentages. The examination section appears to be processing "
            "applications without cross-checking attendance data from the academic section."
        ),
        "category": "Academic",
        "incident_date": "2025-11-15",
    },
    # 9. Ambiguous — possible overlap
    {
        "demo_id": "SYNTH-009",
        "scenario_name": "Possible Semantic Duplicate — Needs Human Review",
        "expected_outcome": "NEEDS_HUMAN_REVIEW",
        "permanent_id": _VALID_PID_PLACEHOLDER,
        "subject": "Students not receiving caution deposit refund despite requests",
        "description": (
            "Multiple students who completed their programs in May 2025 have not received their caution deposit "
            "back from the institution. The total amount withheld is approximately Rs 3,75,000 across 25 students. "
            "Refund applications were submitted between June and August 2025. The accounts office has not "
            "provided any timeline and refuses to respond to written requests. This is a repeat issue reported "
            "in previous academic years as well."
        ),
        "category": "Financial",
        "incident_date": "2025-06-01",
    },
    # 10. Genuinely different valid submission from second institution — should PASS
    {
        "demo_id": "SYNTH-010",
        "scenario_name": "Valid Second Institution Submission",
        "expected_outcome": "PASSED",
        "permanent_id": _VALID_PID_2_PLACEHOLDER,
        "subject": "Non-compliance with AICTE mandatory disclosure requirements",
        "description": (
            "The institution has not updated its mandatory disclosure on the AICTE portal for the academic year "
            "2025-26 despite the submission deadline having passed. The mandatory disclosure includes faculty "
            "qualifications, infrastructure details, admission statistics, and fee structure. Without this "
            "information being publicly available, students cannot make informed decisions about admissions. "
            "This non-compliance has been ongoing for at least three consecutive years per portal records."
        ),
        "category": "Academic",
        "incident_date": "2025-09-01",
        "contact_info": "student.association@example.edu",
    },
]

# ==============================================================================
# 8 DOCUMENT-SPECIFIC DEMONSTRATION SCENARIOS (Testing Real Upload & Verification)
# ==============================================================================

DOCUMENT_SUBMISSIONS: list[dict[str, Any]] = [
    # DOC-001: Valid complaint with matching fee receipt document — should PASS
    {
        "demo_id": "DOC-001",
        "scenario_name": "Valid Financial Complaint with Matching Fee Receipt Document",
        "expected_outcome": "PASSED",
        "permanent_id": _VALID_PID_2_PLACEHOLDER,
        "category": "Financial",
        "subject": "Delay in refund of institutional caution deposit after graduation",
        "description": (
            "The complainant completed degree requirements in June 2025 and applied for refund of the Rs 15,000 "
            "caution deposit on 15 July 2025. As per AICTE Approval Process Handbook guidelines, institutional "
            "caution deposits must be returned upon graduation within thirty days. Attached is the official "
            "fee receipt issued by the college accounts department at the time of admission."
        ),
        "incident_date": "2025-07-15",
        "contact_info": "alumni.rep@example.com",
        "document_attachments": [
            {
                "filename": "caution_deposit_receipt.txt",
                "content_type": "text/plain",
                "content": (
                    "INSTITUTE OF TECHNOLOGY AND MANAGEMENT\n"
                    "ACCOUNTS DEPARTMENT - OFFICIAL RECEIPT\n"
                    "Receipt No: REC-2025-09841\n"
                    "Date: 15-08-2021\n"
                    "Student Name: Rajesh Kumar\n"
                    "Fee Head: Caution Deposit\n"
                    "Amount: Rs. 15,000.00\n"
                    "Payment Mode: Bank Challan\n"
                    "Authorized Signatory\n"
                ),
            }
        ],
    },
    # DOC-002: Missing mandatory evidence for financial complaint — should REJECT_AT_INTAKE
    {
        "demo_id": "DOC-002",
        "scenario_name": "Missing Mandatory Supporting Document (Financial Grievance)",
        "expected_outcome": "REJECTED_AT_INTAKE",
        "permanent_id": _VALID_PID_PLACEHOLDER,
        "category": "Financial",
        "subject": "Excessive development fee collected from postgraduate students",
        "description": (
            "The institution allegedly levied an unauthorized development fee of Rs 40,000 during "
            "the academic session 2025-26. Students have verbally protested to the dean, but no "
            "written response was given. Complainant alleges this violates AICTE fee regulations."
        ),
        "incident_date": "2025-10-01",
        "contact_info": "student.welfare@example.com",
        "document_attachments": [],  # Empty document list triggers MISSING_MANDATORY_EVIDENCE
    },
    # DOC-003: Unreadable or corrupted document — should REJECT_AT_INTAKE
    {
        "demo_id": "DOC-003",
        "scenario_name": "Unreadable or Corrupted Uploaded Document",
        "expected_outcome": "REJECTED_AT_INTAKE",
        "permanent_id": _VALID_PID_PLACEHOLDER,
        "category": "Academic",
        "subject": "Arbitrary grading in semester examination and withheld grade cards",
        "description": (
            "The department withheld semester five grade cards without providing justification. "
            "Students requested the grade transcripts on multiple occasions. The attached scan "
            "contains the representation submitted to the controller of examinations."
        ),
        "incident_date": "2025-11-20",
        "document_attachments": [
            {
                "filename": "representation_scan_damaged.pdf",
                "content_type": "application/pdf",
                "content": "%PDF-1.4\n%DAMAGED_CORRUPTED_STREAM_NULL_ZERO_BYTES\x00\x00\x00",
            }
        ],
    },
    # DOC-004: Irrelevant document (electricity utility bill) — should REJECT_AT_INTAKE
    {
        "demo_id": "DOC-004",
        "scenario_name": "Irrelevant Document Attached to Complaint",
        "expected_outcome": "REJECTED_AT_INTAKE",
        "permanent_id": _VALID_PID_PLACEHOLDER,
        "category": "Financial",
        "subject": "Dispute regarding caution money reimbursement at college",
        "description": (
            "The accounts office has not disbursed caution money refund to graduating students. "
            "Complainant uploaded the documentation provided to the administrative desk."
        ),
        "incident_date": "2025-08-10",
        "document_attachments": [
            {
                "filename": "commercial_power_tariff.txt",
                "content_type": "text/plain",
                "content": (
                    "STATE ELECTRICITY DISTRIBUTION CORPORATION\n"
                    "Monthly commercial electricity utility bill energy meter power tariff payment receipt consumer invoice.\n"
                    "Consumer ID: 9948210349\n"
                    "Billing Month: October 2025\n"
                    "Units Consumed: 1420 kWh\n"
                    "Amount Payable: Rs 11,450.00\n"
                ),
            }
        ],
    },
    # DOC-005: Institution identity mismatch between form and document — should REJECT_AT_INTAKE
    {
        "demo_id": "DOC-005",
        "scenario_name": "Institution Identity Mismatch Between Form and Document",
        "expected_outcome": "REJECTED_AT_INTAKE",
        "permanent_id": _VALID_PID_PLACEHOLDER,
        "category": "Financial",
        "subject": "Non-refund of caution deposit fee upon academic withdrawal",
        "description": (
            "Complainant withdrew admission within the prescribed AICTE timeline and requested a refund. "
            "The attached receipt confirms deposit of caution money at the time of admission."
        ),
        "incident_date": "2025-09-05",
        "document_attachments": [
            {
                "filename": "fee_receipt_other_institution.txt",
                "content_type": "text/plain",
                "content": (
                    "ST. XAVIER ADVANCED INSTITUTE OF PHARMACEUTICAL STUDIES\n"
                    "Official Receipt for Caution Money\n"
                    "Receipt No: SX-2025-4412\n"
                    "Date: 05-09-2025\n"
                    "Student: Vikramaditya Singh\n"
                    "Amount: Rs. 25,000.00\n"
                    "Authorized Cashier\n"
                ),
            }
        ],
    },
    # DOC-006: Conflicting amounts across two documents — should require CORRECTION_REQUIRED
    {
        "demo_id": "DOC-006",
        "scenario_name": "Contradictory Information Across Multiple Uploaded Documents",
        "expected_outcome": "CORRECTION_REQUIRED",
        "permanent_id": _VALID_PID_2_PLACEHOLDER,
        "category": "Financial",
        "subject": "Discrepancy in institutional caution money refund claim",
        "description": (
            "The student submitted duplicate receipt copies for caution money refund. "
            "The administration office has declined processing citing numerical inconsistencies "
            "between the claim voucher and original fee receipt submitted."
        ),
        "incident_date": "2025-10-15",
        "document_attachments": [
            {
                "filename": "student_receipt_original.txt",
                "content_type": "text/plain",
                "content": (
                    "INSTITUTE OF TECHNOLOGY AND MANAGEMENT\n"
                    "RECEIPT OF PAYMENT\n"
                    "Receipt No: REC-001\n"
                    "Date: 15-08-2025\n"
                    "Towards: Caution Deposit\n"
                    "Amount: Rs. 15,000.00\n"
                ),
            },
            {
                "filename": "student_claim_voucher.txt",
                "content_type": "text/plain",
                "content": (
                    "INSTITUTE OF TECHNOLOGY AND MANAGEMENT\n"
                    "RECEIPT OF PAYMENT\n"
                    "Receipt No: REC-002\n"
                    "Date: 15-08-2025\n"
                    "Towards: Caution Deposit\n"
                    "Amount: Rs. 85,000.00\n"
                ),
            },
        ],
    },
    # DOC-007: Duplicate complaint evidence — should be flagged
    {
        "demo_id": "DOC-007",
        "scenario_name": "Potential Duplicate Complaint Text & Evidence",
        "expected_outcome": "NEEDS_HUMAN_REVIEW",
        "permanent_id": _VALID_PID_PLACEHOLDER,
        "category": "Financial",
        "subject": "Delay in refund of caution money collected at admission",
        "description": (
            "The institution collected a caution money deposit of Rs 15,000 at the time of admission in August 2025. "
            "As per AICTE guidelines, this amount is refundable upon request after course completion or withdrawal. "
            "The student submitted a refund application on 15 September 2025, with all required supporting documents. "
            "Despite multiple follow-ups with the administration office on 01 October and 15 October 2025, "
            "no refund has been issued. The institution has not provided any written communication explaining the delay. "
            "This constitutes a violation of financial norms applicable to AICTE-approved institutions."
        ),
        "incident_date": "2025-09-15",
        "document_attachments": [
            {
                "filename": "caution_deposit_duplicate.txt",
                "content_type": "text/plain",
                "content": (
                    "INSTITUTE OF TECHNOLOGY AND MANAGEMENT\n"
                    "ACCOUNTS DEPARTMENT - OFFICIAL RECEIPT\n"
                    "Receipt No: REC-2025-09841\n"
                    "Date: 15-08-2021\n"
                    "Student Name: Rajesh Kumar\n"
                    "Fee Head: Caution Deposit\n"
                    "Amount: Rs. 15,000.00\n"
                    "Payment Mode: Bank Challan\n"
                    "Authorized Signatory\n"
                ),
            }
        ],
    },
    # DOC-008: Ambiguous document requiring human review
    {
        "demo_id": "DOC-008",
        "scenario_name": "Ambiguous Document Requiring Human Review",
        "expected_outcome": "NEEDS_HUMAN_REVIEW",
        "permanent_id": _VALID_PID_PLACEHOLDER,
        "category": "Academic",
        "subject": "Representation on library and computing lab availability hours",
        "description": (
            "Students across semester five submitted a representation requesting extension of evening "
            "computing facility hours. The attached document contains informal meeting minutes and student notes."
        ),
        "incident_date": "2025-10-10",
        "document_attachments": [
            {
                "filename": "informal_meeting_notes.txt",
                "content_type": "text/plain",
                "content": (
                    "Student Committee Meeting Notes - Library Timings\n"
                    "Date: 10-10-2025\n"
                    "Discussion regarding access to computer centers after 6 PM.\n"
                    "Representatives met with the lab assistant. Decision pending.\n"
                ),
            }
        ],
    },
]
