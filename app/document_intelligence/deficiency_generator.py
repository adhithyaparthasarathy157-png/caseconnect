"""Deficiency Notice Generator for AI Document Intelligence.

Synthesizes detected findings into an official, polite, and legally actionable
AICTE Pre-Scrutiny Deficiency Notice addressed to the institution head.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.document_intelligence.schemas import (
    DocumentCategory,
    FindingSeverity,
    ValidationFinding,
)


def generate_deficiency_notice(
    case_id: str,
    institution_name: str,
    institution_identifier: str | None,
    document_type: str,
    findings: list[ValidationFinding],
) -> str | None:
    """Generates an official AICTE Pre-Scrutiny Deficiency Communication.
    
    Returns None if there are no actionable (Critical or Warning) findings.
    """
    actionable_findings = [
        f for f in findings
        if f.severity in (FindingSeverity.CRITICAL, FindingSeverity.WARNING) and not f.dismissed
    ]

    if not actionable_findings:
        return None

    today_str = datetime.now().strftime("%d %B %Y")
    inst_ref = f" (ID: {institution_identifier})" if institution_identifier else ""

    lines: list[str] = [
        "ALL INDIA COUNCIL FOR TECHNICAL EDUCATION (AICTE)",
        "Nelson Mandela Marg, Vasant Kunj, New Delhi - 110070",
        "PRE-SCRUTINY COMPLIANCE DEFICIENCY NOTICE",
        "--------------------------------------------------------------------------------",
        f"Notice Ref: AICTE/SCRUTINY/{case_id}/{datetime.now().strftime('%Y%m%d')}",
        f"Date: {today_str}",
        f"Case Reference: {case_id}",
        "",
        "TO:",
        f"The Principal / Head of Institution,",
        f"{institution_name}{inst_ref}",
        "",
        f"SUBJECT: Pre-Scrutiny Deficiencies Identified in Submitted '{document_type}'",
        "",
        "Sir / Madam,",
        "",
        f"During the pre-scrutiny examination of the documents uploaded in connection with Case Reference {case_id}, "
        f"the following deficiencies and regulatory non-compliances were detected in the submitted '{document_type}':",
        "",
    ]

    for idx, f in enumerate(actionable_findings, start=1):
        lines.append(f"{idx}. DEFICIENCY AREA: {f.field_name.replace('_', ' ').upper()} [{f.severity.value.upper()}]")
        lines.append(f"   - Observation: {f.explanation}")
        if f.detected_value is not None:
            lines.append(f"   - Detected Value: {f.detected_value}")
        lines.append(f"   - Regulatory Norm: {f.expected_condition}")
        lines.append(f"   - Required Corrective Action: {f.suggested_correction}")
        if f.evidence_snippet:
            lines.append(f"   - Extracted Evidence: \"{f.evidence_snippet}\"")
        lines.append("")

    lines.extend([
        "DIRECTIVE & REMEDIATION TIMELINE:",
        "You are hereby instructed to rectify the aforementioned deficiencies and upload the duly certified / amended ",
        "documents on the AICTE CaseConnect Portal within seven (7) working days of this communication.",
        "Failure to submit valid rectification within the stipulated period may result in adverse regulatory determinations ",
        "pursuant to the AICTE Approval Process Handbook (APH) regulations.",
        "",
        "Issued by Authority,",
        "Office of the Scrutiny Committee & Approval Bureau,",
        "All India Council for Technical Education (AICTE)",
    ])

    return "\n".join(lines)
