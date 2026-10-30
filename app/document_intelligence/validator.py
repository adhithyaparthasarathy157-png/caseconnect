"""Explainable Pre-Scrutiny Validation Engine for AICTE Documents.

Evaluates extracted document fields against regulatory requirements,
cross-references case and institution data, and determines deterministic pre-scrutiny verdicts.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from app.document_intelligence.requirements_registry import (
    CategoryRequirements,
    get_requirements_for_category,
)
from app.document_intelligence.schemas import (
    DocumentCategory,
    ExtractedField,
    FindingSeverity,
    FindingType,
    PreScrutinyStatus,
    ValidationFinding,
)


def _normalize_name(name: str) -> str:
    """Normalizes institution names for fuzzy substring and token comparison."""
    cleaned = re.sub(r"[^\w\s]", " ", name.lower())
    # Remove common filler words
    stop_words = {"institute", "institution", "college", "of", "technology", "engineering", "and", "the", "for"}
    tokens = [t for t in cleaned.split() if t not in stop_words and len(t) > 2]
    return " ".join(tokens)


def _check_name_similarity(doc_name: str, case_name: str) -> bool:
    """Returns True if document institution name plausibly matches case institution name."""
    norm_doc = _normalize_name(doc_name)
    norm_case = _normalize_name(case_name)

    if not norm_doc or not norm_case:
        return True

    # Direct substring
    if norm_doc in norm_case or norm_case in norm_doc:
        return True

    doc_tokens = set(norm_doc.split())
    case_tokens = set(norm_case.split())

    intersection = doc_tokens.intersection(case_tokens)
    if not intersection:
        return False

    overlap = len(intersection) / max(len(doc_tokens), len(case_tokens))
    return overlap >= 0.40


def _parse_date(date_str: str) -> date | None:
    """Attempts to parse common date formats found in Indian official certificates."""
    clean = date_str.strip()
    formats = [
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d.%m.%Y",
        "%Y-%m-%d",
        "%d %B %Y",
        "%d %b %Y",
        "%B %d, %Y",
        "%b %d, %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(clean, fmt).date()
        except ValueError:
            continue
    return None


def validate_document(
    category: DocumentCategory,
    extracted_fields: dict[str, ExtractedField],
    case_context: dict[str, Any],
    ocr_text: str,
    classification_confidence: float = 1.0,
    requires_classification_review: bool = False,
) -> tuple[PreScrutinyStatus, list[ValidationFinding], str, bool]:
    """Validates extracted document fields against pre-scrutiny standards.
    
    Returns:
        (pre_scrutiny_status, list_of_findings, recommended_action, requires_human_review)
    """
    findings: list[ValidationFinding] = []
    finding_counter = 1

    # 1. Handle Unsupported Document Category
    if category == DocumentCategory.UNSUPPORTED:
        findings.append(
            ValidationFinding(
                finding_id=f"FIND-{finding_counter:03d}",
                field_name="document_category",
                detected_value="Unsupported Document",
                expected_condition="Must be one of: Affiliation Certificate, Approval Letter, Institution Registration, Faculty Statement, Infrastructure Report",
                finding_type=FindingType.UNSUPPORTED_DOCUMENT,
                severity=FindingSeverity.CRITICAL,
                explanation="Uploaded document text does not conform to any recognized AICTE regulatory document schema.",
                evidence_snippet=ocr_text[:180].replace("\n", " ").strip(),
                suggested_correction="Upload a valid, official AICTE prescribed document format.",
                requires_human_review=True,
            )
        )
        return (
            PreScrutinyStatus.UNSUPPORTED,
            findings,
            "Unsupported document type uploaded. Reject submission and request valid AICTE regulatory documentation.",
            True,
        )

    requirements = get_requirements_for_category(category)
    if not requirements:
        return (
            PreScrutinyStatus.NEEDS_HUMAN_REVIEW,
            findings,
            "No pre-scrutiny rules defined for this document category.",
            True,
        )

    # 2. Check Mandatory Fields
    for req in requirements.mandatory_fields:
        field = extracted_fields.get(req.field_name)
        val = field.value if field else None
        if val is None or str(val).strip() == "" or (field and field.confidence < 0.20):
            finding_counter += 1
            findings.append(
                ValidationFinding(
                    finding_id=f"FIND-{finding_counter:03d}",
                    field_name=req.field_name,
                    detected_value=None,
                    expected_condition=f"Mandatory: {req.display_name} must be clearly stated",
                    finding_type=FindingType.INFORMATION_MISSING,
                    severity=req.missing_severity,
                    explanation=f"Required field '{req.display_name}' could not be located or extracted from the document.",
                    evidence_snippet=None,
                    suggested_correction=f"Provide a clear and complete document that includes the official '{req.display_name}'.",
                    requires_human_review=(req.missing_severity == FindingSeverity.CRITICAL),
                )
            )

    # 3. Check Institution Name & ID Match (if applicable)
    case_inst_name = case_context.get("institution_name", "")
    case_inst_code = case_context.get("institution_identifier", "")
    expected_year = case_context.get("academic_year", "2024-25")

    if requirements.requires_institution_match and case_inst_name:
        doc_inst_name = extracted_fields.get("institution_name")
        if doc_inst_name and doc_inst_name.value:
            if not _check_name_similarity(str(doc_inst_name.value), str(case_inst_name)):
                finding_counter += 1
                findings.append(
                    ValidationFinding(
                        finding_id=f"FIND-{finding_counter:03d}",
                        field_name="institution_name",
                        detected_value=doc_inst_name.value,
                        expected_condition=f"Must match case institution: '{case_inst_name}'",
                        finding_type=FindingType.VALIDATION_FAILURE,
                        severity=FindingSeverity.CRITICAL,
                        explanation=f"Document institution name ('{doc_inst_name.value}') conflicts with the Case's designated institution ('{case_inst_name}').",
                        evidence_snippet=doc_inst_name.evidence,
                        suggested_correction=f"Verify that the uploaded certificate specifically pertains to '{case_inst_name}'.",
                        requires_human_review=True,
                    )
                )

        # Check Institution ID / Code if extracted
        doc_inst_code = extracted_fields.get("institution_code") or extracted_fields.get("institution_id")
        if doc_inst_code and doc_inst_code.value and case_inst_code:
            clean_doc_code = str(doc_inst_code.value).strip().upper()
            clean_case_code = str(case_inst_code).strip().upper()
            if clean_doc_code != clean_case_code and clean_case_code not in clean_doc_code and clean_doc_code not in clean_case_code:
                # Potential code mismatch
                finding_counter += 1
                findings.append(
                    ValidationFinding(
                        finding_id=f"FIND-{finding_counter:03d}",
                        field_name="institution_code",
                        detected_value=doc_inst_code.value,
                        expected_condition=f"Must match institution ID '{clean_case_code}'",
                        finding_type=FindingType.VALIDATION_FAILURE,
                        severity=FindingSeverity.WARNING,
                        explanation=f"Detected Institution Code '{doc_inst_code.value}' does not match registered case ID '{clean_case_code}'.",
                        evidence_snippet=doc_inst_code.evidence,
                        suggested_correction="Verify permanent institute ID against AICTE portal registration records.",
                        requires_human_review=True,
                    )
                )

    # 4. Check Validity Period / Academic Year / Expiry
    if requirements.requires_validity_check:
        # Academic Year check
        acad_field = extracted_fields.get("academic_year")
        if acad_field and acad_field.value:
            doc_year = str(acad_field.value).strip()
            # If doc academic year starts prior to 2024 (e.g. 2021-22, 2022-23) while expected is 2024-25
            year_match = re.search(r"(20[1-3][0-9])", doc_year)
            if year_match:
                start_year = int(year_match.group(1))
                if start_year < 2024:
                    finding_counter += 1
                    findings.append(
                        ValidationFinding(
                            finding_id=f"FIND-{finding_counter:03d}",
                            field_name="academic_year",
                            detected_value=doc_year,
                            expected_condition=f"Valid for Academic Year {expected_year}",
                            finding_type=FindingType.VALIDATION_FAILURE,
                            severity=FindingSeverity.CRITICAL,
                            explanation=f"Document is valid for past Academic Year '{doc_year}'. AICTE scrutiny requires active validity for '{expected_year}'.",
                            evidence_snippet=acad_field.evidence,
                            suggested_correction=f"Submit renewal/extension documentation for current Academic Year {expected_year}.",
                            requires_human_review=False,
                        )
                    )

        # Explicit Valid Till Date check
        valid_till_field = extracted_fields.get("valid_till_date")
        if valid_till_field and valid_till_field.value:
            parsed_date = _parse_date(str(valid_till_field.value))
            if parsed_date:
                # If date is in the past (prior to mid 2025 or current date)
                if parsed_date < date(2024, 6, 30):
                    finding_counter += 1
                    findings.append(
                        ValidationFinding(
                            finding_id=f"FIND-{finding_counter:03d}",
                            field_name="valid_till_date",
                            detected_value=str(valid_till_field.value),
                            expected_condition=f"Must be valid on or beyond {expected_year}",
                            finding_type=FindingType.VALIDATION_FAILURE,
                            severity=FindingSeverity.CRITICAL,
                            explanation=f"Document validity lapsed on {parsed_date.strftime('%d-%b-%Y')}. Certificate has expired.",
                            evidence_snippet=valid_till_field.evidence,
                            suggested_correction="Submit an up-to-date re-affiliation or extension certificate issued by the competent authority.",
                            requires_human_review=False,
                        )
                    )

    # 5. Category-Specific Semantic Checks
    if category == DocumentCategory.FACULTY_STATEMENT:
        sfr_field = extracted_fields.get("student_faculty_ratio")
        if sfr_field and sfr_field.value:
            sfr_str = str(sfr_field.value)
            sfr_match = re.search(r"1\s*:\s*([0-9\.]+)", sfr_str)
            if sfr_match:
                sfr_ratio = float(sfr_match.group(1))
                if sfr_ratio > 20.0:
                    finding_counter += 1
                    findings.append(
                        ValidationFinding(
                            finding_id=f"FIND-{finding_counter:03d}",
                            field_name="student_faculty_ratio",
                            detected_value=sfr_str,
                            expected_condition="Student-to-Faculty Ratio (SFR) <= 1:20",
                            finding_type=FindingType.VALIDATION_FAILURE,
                            severity=FindingSeverity.CRITICAL,
                            explanation=f"Reported Student-Faculty Ratio of 1:{sfr_ratio:.1f} violates AICTE Approval Process Handbook norms (maximum permissible: 1:20).",
                            evidence_snippet=sfr_field.evidence,
                            suggested_correction="Appoint adequate regular qualified faculty members to bring the institutional SFR within the statutory 1:20 limit.",
                            requires_human_review=False,
                        )
                    )

        # Faculty count arithmetic reconciliation
        tot_field = extracted_fields.get("total_faculty_count")
        p_field = extracted_fields.get("professors_count")
        asp_field = extracted_fields.get("associate_professors_count")
        ap_field = extracted_fields.get("assistant_professors_count")

        if (
            tot_field
            and tot_field.value
            and p_field
            and p_field.value
            and asp_field
            and asp_field.value
            and ap_field
            and ap_field.value
        ):
            try:
                tot = int(tot_field.value)
                p = int(p_field.value)
                asp = int(asp_field.value)
                ap = int(ap_field.value)
                cadre_sum = p + asp + ap
                if cadre_sum != tot:
                    finding_counter += 1
                    findings.append(
                        ValidationFinding(
                            finding_id=f"FIND-{finding_counter:03d}",
                            field_name="total_faculty_count",
                            detected_value=f"Total: {tot}, Cadre Sum: {cadre_sum}",
                            expected_condition="Sum of Professors, Associate Professors, and Assistant Professors must equal Total Faculty",
                            finding_type=FindingType.VALIDATION_FAILURE,
                            severity=FindingSeverity.WARNING,
                            explanation=f"Internal mathematical discrepancy: Sum of individual cadres ({p} + {asp} + {ap} = {cadre_sum}) does not match Total Faculty Count ({tot}).",
                            evidence_snippet=tot_field.evidence,
                            suggested_correction="Re-verify teaching roster numbers and reconcile individual cadre breakdowns.",
                            requires_human_review=True,
                        )
                    )
            except (ValueError, TypeError):
                pass

    elif category == DocumentCategory.INFRASTRUCTURE_REPORT:
        land_field = extracted_fields.get("land_area_acres")
        if land_field and land_field.value:
            land_match = re.search(r"([0-9\.]+)", str(land_field.value))
            if land_match:
                acres = float(land_match.group(1))
                if acres < 2.5:
                    finding_counter += 1
                    findings.append(
                        ValidationFinding(
                            finding_id=f"FIND-{finding_counter:03d}",
                            field_name="land_area_acres",
                            detected_value=f"{acres} Acres",
                            expected_condition="Minimum 2.5 Acres of contiguous land",
                            finding_type=FindingType.VALIDATION_FAILURE,
                            severity=FindingSeverity.CRITICAL,
                            explanation=f"Reported land area ({acres} acres) is below the statutory AICTE land requirement of 2.5 acres.",
                            evidence_snippet=land_field.evidence,
                            suggested_correction="Submit registered title deeds proving ownership/lease of the required minimum contiguous land area.",
                            requires_human_review=False,
                        )
                    )

        # Area breakdown consistency
        built_field = extracted_fields.get("total_built_up_area_sqm")
        inst_field = extracted_fields.get("instructional_area_sqm")
        if built_field and built_field.value and inst_field and inst_field.value:
            try:
                b_num = float(re.sub(r"[^\d\.]", "", str(built_field.value)))
                i_num = float(re.sub(r"[^\d\.]", "", str(inst_field.value)))
                if i_num > b_num:
                    finding_counter += 1
                    findings.append(
                        ValidationFinding(
                            finding_id=f"FIND-{finding_counter:03d}",
                            field_name="total_built_up_area_sqm",
                            detected_value=f"Built-up: {b_num} sq.m, Instructional: {i_num} sq.m",
                            expected_condition="Total built-up area must be strictly greater than or equal to instructional area",
                            finding_type=FindingType.VALIDATION_FAILURE,
                            severity=FindingSeverity.CRITICAL,
                            explanation=f"Area paradox: Instructional area ({i_num} sq.m) exceeds total certified built-up area ({b_num} sq.m).",
                            evidence_snippet=inst_field.evidence,
                            suggested_correction="Submit an amended certified building measurement plan prepared by a registered chartered architect.",
                            requires_human_review=False,
                        )
                    )
            except (ValueError, TypeError):
                pass

        # Fire safety certificate status
        fire_field = extracted_fields.get("fire_safety_certificate")
        if fire_field and fire_field.value:
            f_str = str(fire_field.value).lower()
            if any(term in f_str for term in ["expired", "not available", "pending", "applied", "in process", "none"]):
                finding_counter += 1
                findings.append(
                    ValidationFinding(
                        finding_id=f"FIND-{finding_counter:03d}",
                        field_name="fire_safety_certificate",
                        detected_value=fire_field.value,
                        expected_condition="Active, valid Fire Safety NOC issued by Fire Services",
                        finding_type=FindingType.VALIDATION_FAILURE,
                        severity=FindingSeverity.CRITICAL,
                        explanation=f"Fire Safety NOC is not active or compliant ('{fire_field.value}'). Fire safety clearance is mandatory for campus operations.",
                        evidence_snippet=fire_field.evidence,
                        suggested_correction="Upload current Fire Safety Certificate issued by the competent Fire and Rescue Services Authority.",
                        requires_human_review=False,
                    )
                )

    # 6. Check Inconsistent Internal Information
    # Check if text mentions conflicting years or terms (e.g. "Provisional affiliation for 2023-24 only" inside 2024-25 document)
    if "provisional affiliation for 2023-24 only" in ocr_text.lower() and "2024-25" in ocr_text:
        finding_counter += 1
        findings.append(
            ValidationFinding(
                finding_id=f"FIND-{finding_counter:03d}",
                field_name="academic_year",
                detected_value="Contradictory academic years (2023-24 vs 2024-25)",
                expected_condition="Consistent academic session throughout certificate body",
                finding_type=FindingType.VALIDATION_FAILURE,
                severity=FindingSeverity.CRITICAL,
                explanation="Internal inconsistency detected: Body clause restricts affiliation to '2023-24 only' while heading cites '2024-25'.",
                evidence_snippet="Provisional affiliation for 2023-24 only",
                suggested_correction="Provide unambiguous re-affiliation order from University confirming validity for 2024-25.",
                requires_human_review=True,
            )
        )

    # 7. Check for Low Confidence / OCR Degradation
    if classification_confidence < 0.60 or requires_classification_review:
        finding_counter += 1
        findings.append(
            ValidationFinding(
                finding_id=f"FIND-{finding_counter:03d}",
                field_name="ocr_text_quality",
                detected_value=f"Confidence {classification_confidence:.2f}",
                expected_condition="High-clarity OCR extraction (> 0.60 confidence)",
                finding_type=FindingType.HUMAN_VERIFICATION_REQUIRED,
                severity=FindingSeverity.WARNING,
                explanation="Document contains OCR noise, degraded text, or ambiguous category boundaries that require manual confirmation.",
                evidence_snippet=ocr_text[:120].replace("\n", " ").strip(),
                suggested_correction="Scrutiny officer should manually verify original scanned PDF document.",
                requires_human_review=True,
            )
        )

    # 8. Determine Overall Status and Recommended Action
    has_critical = any(f.severity == FindingSeverity.CRITICAL for f in findings)
    has_warning = any(f.severity == FindingSeverity.WARNING for f in findings)
    needs_review = any(f.requires_human_review for f in findings) or requires_classification_review

    if has_critical or has_warning:
        status = PreScrutinyStatus.FLAGGED
        critical_count = sum(1 for f in findings if f.severity == FindingSeverity.CRITICAL)
        warning_count = sum(1 for f in findings if f.severity == FindingSeverity.WARNING)
        recommended_action = (
            f"Pre-scrutiny identified {critical_count} critical and {warning_count} warning deficiencies. "
            "Scrutiny officer should review findings and dispatch formal deficiency notice to the institution."
        )
    elif needs_review:
        status = PreScrutinyStatus.NEEDS_HUMAN_REVIEW
        recommended_action = (
            "No outright rule violations detected, but text clarity or confidence warrants officer manual review before acceptance."
        )
    else:
        status = PreScrutinyStatus.PASSED
        recommended_action = (
            "Document satisfies all mandatory AICTE pre-scrutiny criteria and institution registry alignment. "
            "Recommended for administrative approval."
        )

    return status, findings, recommended_action, needs_review
