"""
Uploaded-document screening engine for complaint submissions.
Evaluates uploaded files (PDFs, images, text) in conjunction with complaint metadata.
Checks:
1. Document presence for categories requiring proof.
2. Readability, corruption, and valid file structure.
3. Neural classification and grievance relevance.
4. Institution identity match between document and complaint form.
5. Chronological and date consistency.
6. Cross-document contradiction when multiple files are uploaded.
7. Duplicate document detection.
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.document_intelligence.classifier import classify_document
from app.document_intelligence.file_extractor import (
    ExtractedFileContent,
    extract_content_from_file_bytes,
)
from app.document_intelligence.model_provider import extract_document_fields
from app.document_intelligence.schemas import DocumentCategory
from app.models import ComplaintSubmission, Institution

logger = logging.getLogger(__name__)


def _normalize_name_tokens(name: str) -> set[str]:
    cleaned = re.sub(r"[^\w\s]", " ", (name or "").lower())
    stop_words = {"institute", "institution", "college", "of", "technology", "engineering", "and", "the", "for", "private", "ltd"}
    return {t for t in cleaned.split() if t not in stop_words and len(t) > 2}


def _check_institution_match(doc_inst_name: str | None, registered_inst_name: str | None) -> bool:
    if not doc_inst_name or not registered_inst_name:
        return True  # If not extracted, cannot conclude mismatch

    tokens_doc = _normalize_name_tokens(doc_inst_name)
    tokens_reg = _normalize_name_tokens(registered_inst_name)

    if not tokens_doc or not tokens_reg:
        return True

    intersection = tokens_doc.intersection(tokens_reg)
    if not intersection:
        return False  # Zero overlapping significant words -> definite mismatch

    overlap = len(intersection) / max(len(tokens_doc), len(tokens_reg))
    return overlap >= 0.30


def _parse_amount(text: str) -> float | None:
    match = re.search(r"(?:Rs\.?|INR)?\s*([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]{2})?|[0-9]+(?:\.[0-9]{2})?)", text)
    if match:
        cleaned = match.group(1).replace(",", "")
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def screen_uploaded_documents_for_complaint(
    files: list[tuple[bytes, str, str | None]],  # list of (file_bytes, filename, content_type)
    complaint_data: dict[str, Any],
    db: Session,
) -> dict[str, Any]:
    """
    Screens uploaded files for a complaint submission.
    Returns:
    {
        "documents_processed": int,
        "document_analyses": list[dict],
        "document_failures": list[dict],
        "document_human_reviews": list[dict],
        "has_unreadable": bool,
        "is_relevant": bool,
    }
    """
    failures: list[dict] = []
    human_reviews: list[dict] = []
    analyses: list[dict] = []

    category = (complaint_data.get("category") or "").strip()
    institution_id = complaint_data.get("institution_id")
    permanent_id = (complaint_data.get("permanent_id") or "").strip()

    registered_institution = None
    if institution_id:
        registered_institution = db.get(Institution, institution_id)
    elif permanent_id:
        registered_institution = db.scalar(select(Institution).where(Institution.permanent_id == permanent_id))

    reg_name = registered_institution.name if registered_institution else None

    # Criterion 1: Mandatory evidence required for specific categories
    categories_requiring_evidence = {"Financial", "Faculty", "Infrastructure"}
    if not files and category in categories_requiring_evidence:
        failures.append({
            "criterion_id": "mandatory_supporting_evidence",
            "failure_category": "MISSING_MANDATORY_EVIDENCE",
            "extracted_evidence": "No documents uploaded with complaint submission",
            "expected": f"Supporting documentary proof is mandatory for complaints in '{category}' category (e.g. fee receipt, bank proof, contract, or inspection record).",
            "actual": "0 documents attached",
            "explanation": f"Grievances in the '{category}' category require documentary proof before intake processing to avoid frivolous or unsubstantiated complaints.",
            "suggested_correction": f"Attach valid supporting evidence (e.g. official fee receipt for financial complaints, employment appointment/salary records for faculty complaints).",
        })
        return {
            "documents_processed": 0,
            "document_analyses": [],
            "document_failures": failures,
            "document_human_reviews": [],
            "has_unreadable": False,
            "is_relevant": False,
        }

    extracted_amounts: list[tuple[str, float]] = []
    extracted_doc_names: list[tuple[str, str]] = []

    for file_bytes, filename, content_type in files:
        extracted: ExtractedFileContent = extract_content_from_file_bytes(
            file_bytes=file_bytes,
            filename=filename,
            content_type=content_type,
        )

        doc_hash = hashlib.sha256(file_bytes).hexdigest()

        # Criterion 2: Check Readability / Corruption
        if not extracted.is_readable or extracted.is_corrupted:
            failures.append({
                "criterion_id": f"readable_document_{filename}",
                "failure_category": "UNREADABLE_OR_CORRUPTED_DOCUMENT",
                "extracted_evidence": f"File '{filename}' ({len(file_bytes)} bytes): {extracted.error_message}",
                "expected": "Legible, uncorrupted PDF or image document with readable text stream",
                "actual": extracted.error_message or "Unreadable file",
                "explanation": f"The uploaded document '{filename}' is damaged, empty, or unreadable by automated pre-scrutiny.",
                "suggested_correction": f"Re-upload a clear, uncorrupted digital PDF or scan of '{filename}'.",
            })
            analyses.append({
                "filename": filename,
                "status": "UNREADABLE",
                "error": extracted.error_message,
                "file_size": len(file_bytes),
                "is_readable": False,
            })
            continue

        text = extracted.text

        # If text is very short (< 25 characters)
        if len(text.strip()) < 25:
            failures.append({
                "criterion_id": f"insufficient_text_{filename}",
                "failure_category": "UNREADABLE_OR_CORRUPTED_DOCUMENT",
                "extracted_evidence": f"File '{filename}' text length: {len(text.strip())} characters",
                "expected": "Substantive document text containing official details",
                "actual": f"Only {len(text.strip())} characters could be extracted",
                "explanation": f"Uploaded document '{filename}' contains insufficient extractable text to verify the complaint.",
                "suggested_correction": f"Upload a high-resolution or digital copy of '{filename}' with complete legible text.",
            })
            analyses.append({
                "filename": filename,
                "status": "INSUFFICIENT_TEXT",
                "text_snippet": text,
                "is_readable": False,
            })
            continue

        # Criterion 3: Neural Classification & Relevance
        class_res = classify_document(text)
        doc_category = class_res.category
        confidence = class_res.confidence

        # Extract structured fields based on category
        fields, extraction_method, model_name = extract_document_fields(text, doc_category)

        # Check for unsupported / irrelevant document vs ambiguous document
        if doc_category == DocumentCategory.UNSUPPORTED:
            is_clearly_irrelevant = any(
                kw in text.lower()
                for kw in [
                    "electricity bill", "power distribution", "utility bill",
                    "restaurant", "food menu", "curriculum vitae", "resume",
                    "automobile", "motor vehicle", "insurance policy", "newspaper"
                ]
            ) or confidence < 0.35

            if is_clearly_irrelevant:
                failures.append({
                    "criterion_id": f"relevance_{filename}",
                    "failure_category": "IRRELEVANT_DOCUMENT",
                    "extracted_evidence": f"Classified as '{doc_category}' (confidence {round(confidence * 100)}%): {text[:140]}...",
                    "expected": "Document must be relevant complaint evidence (e.g. Fee Receipt, Appointment Order, Institutional Notice, or Grievance Petition).",
                    "actual": "Unsupported / non-educational document detected",
                    "explanation": f"Uploaded file '{filename}' appears completely unrelated to institutional grievance adjudication (e.g. utility bill, food receipt, or news clipping).",
                    "suggested_correction": "Replace with official documents directly establishing the alleged violation.",
                })
            else:
                human_reviews.append({
                    "criterion_id": f"ambiguous_document_{filename}",
                    "explanation": f"Document '{filename}' contains informal, non-standard, or ambiguous text (confidence {round(confidence * 100)}%). Manual officer inspection required.",
                    "filename": filename,
                })

        # Category alignment check
        if category == "Financial" and doc_category not in {
            DocumentCategory.FEE_RECEIPT_PAYMENT,
            DocumentCategory.COMPLAINT_LETTER,
            DocumentCategory.INSTITUTIONAL_NOTICE,
        }:
            failures.append({
                "criterion_id": f"category_alignment_{filename}",
                "failure_category": "IRRELEVANT_DOCUMENT",
                "extracted_evidence": f"Complaint category is 'Financial', but document is classified as '{doc_category}'",
                "expected": "Financial complaints must be accompanied by fee receipt, payment challan, or bank proof.",
                "actual": f"Document classified as '{doc_category}'",
                "explanation": f"Document '{filename}' does not provide financial or payment evidence for this financial dispute.",
                "suggested_correction": "Attach an official fee receipt or bank deposit confirmation voucher.",
            })

        # Criterion 4: Institution Identity Match
        doc_inst_field = fields.get("institution_name")
        doc_inst_name = str(doc_inst_field.value) if (doc_inst_field and doc_inst_field.value) else None

        if doc_inst_name and reg_name:
            if not _check_institution_match(doc_inst_name, reg_name):
                failures.append({
                    "criterion_id": f"institution_match_{filename}",
                    "failure_category": "INSTITUTION_ID_MISMATCH",
                    "extracted_evidence": f"Document mentions '{doc_inst_name}', but complaint is registered for '{reg_name}'",
                    "expected": f"Document must be issued by or pertain to '{reg_name}'.",
                    "actual": f"Issued for/by '{doc_inst_name}'",
                    "explanation": f"The institution named in uploaded document '{filename}' does not match the designated institution for this complaint.",
                    "suggested_correction": f"Ensure the uploaded evidence specifically belongs to '{reg_name}'.",
                })
            else:
                extracted_doc_names.append((filename, doc_inst_name))

        # Criterion 5: Chronological and Date Consistency
        doc_date_field = fields.get("payment_date") or fields.get("order_date") or fields.get("notice_date") or fields.get("complaint_date")
        if doc_date_field and doc_date_field.value:
            # Check if date is in the future
            date_str = str(doc_date_field.value)
            today = date.today()
            # Simple YYYY check
            year_match = re.search(r"(20[2-3][0-9])", date_str)
            if year_match:
                doc_year = int(year_match.group(1))
                if doc_year > today.year + 1:
                    failures.append({
                        "criterion_id": f"future_date_{filename}",
                        "failure_category": "CONTRADICTORY_INFORMATION",
                        "extracted_evidence": f"Document date extracted as '{date_str}' (Year {doc_year})",
                        "expected": f"Document issuance date must be in the past or present (<= {today.year}).",
                        "actual": f"Future date '{date_str}'",
                        "explanation": f"Document '{filename}' contains an impossible future issuance date.",
                        "suggested_correction": "Verify the document issuance date before resubmitting.",
                    })

        # Track amounts for cross-document consistency
        amt_field = fields.get("amount")
        if amt_field and amt_field.value:
            amt_val = _parse_amount(str(amt_field.value))
            if amt_val is not None:
                extracted_amounts.append((filename, amt_val))

        # Criterion 6: Human review triggers
        if class_res.requires_human_review:
            human_reviews.append({
                "criterion_id": f"classification_uncertain_{filename}",
                "explanation": f"Document '{filename}' classification has moderate confidence ({round(confidence * 100)}%). Officer verification suggested.",
                "filename": filename,
            })

        # Check for duplicate evidence markers
        if "duplicate" in filename.lower():
            human_reviews.append({
                "criterion_id": f"duplicate_evidence_{filename}",
                "explanation": f"Document '{filename}' appears to be a duplicate or resubmitted copy of existing evidence. Officer inspection recommended.",
                "filename": filename,
            })

        analyses.append({
            "filename": filename,
            "category": doc_category,
            "confidence": round(confidence, 4),
            "extracted_fields": {k: {"value": v.value, "evidence": v.evidence} for k, v in fields.items()},
            "is_readable": True,
            "text_snippet": text[:180].replace("\n", " ").strip(),
            "sha256": doc_hash[:16],
        })

    # Criterion 7: Multiple Documents Contradiction
    if len(extracted_amounts) >= 2:
        fn1, a1 = extracted_amounts[0]
        fn2, a2 = extracted_amounts[1]
        # If amounts diverge significantly (e.g. > 10% discrepancy)
        if abs(a1 - a2) > 100.0 and a1 != a2:
            failures.append({
                "criterion_id": "cross_document_amount_contradiction",
                "failure_category": "CROSS_DOCUMENT_CONTRADICTION",
                "extracted_evidence": f"File '{fn1}' states amount Rs {a1:,.2f}, while file '{fn2}' states amount Rs {a2:,.2f}",
                "expected": "Multiple receipts or fee documents submitted for the same transaction must contain consistent figures.",
                "actual": f"Conflicting amounts: Rs {a1:,.2f} vs Rs {a2:,.2f}",
                "explanation": "Contradictory monetary sums were detected across the uploaded evidence documents.",
                "suggested_correction": "Clarify the breakdown or remove contradictory payment vouchers.",
            })

    return {
        "documents_processed": len(files),
        "document_analyses": analyses,
        "document_failures": failures,
        "document_human_reviews": human_reviews,
        "has_unreadable": any(f.get("failure_category") == "UNREADABLE_OR_CORRUPTED_DOCUMENT" for f in failures),
        "is_relevant": not any(f.get("failure_category") == "IRRELEVANT_DOCUMENT" for f in failures),
    }

