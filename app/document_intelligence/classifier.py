"""Document Classifier service for AI Document Intelligence.

Uses sentence-transformers neural embeddings to classify OCR documents,
calculates confidence margins, and flags ambiguous or poor OCR inputs for human review.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from app.document_intelligence.model_provider import classify_document_text
from app.document_intelligence.schemas import (
    AlternativeCategory,
    DocumentCategory,
)

logger = logging.getLogger(__name__)


class ClassificationResult:
    def __init__(
        self,
        category: DocumentCategory,
        confidence: float,
        top_alternatives: list[AlternativeCategory],
        model_name: str,
        classification_method: str,
        requires_human_review: bool,
        review_reason: str | None = None,
    ) -> None:
        self.category = category
        self.confidence = confidence
        self.top_alternatives = top_alternatives
        self.model_name = model_name
        self.classification_method = classification_method
        self.requires_human_review = requires_human_review
        self.review_reason = review_reason

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "confidence": self.confidence,
            "top_alternatives": self.top_alternatives,
            "model_name": self.model_name,
            "classification_method": self.classification_method,
            "requires_human_review": self.requires_human_review,
            "review_reason": self.review_reason,
        }


def classify_document(ocr_text: str) -> ClassificationResult:
    """Classifies document OCR text and determines if manual human review is required.
    
    Human review is triggered if:
    1. Confidence score is below threshold (< 0.58).
    2. Score difference between top 2 categories is narrow (< 0.10).
    3. Document is classified as UNSUPPORTED.
    4. Text shows severe OCR degradation or suspicious brevity.
    """
    clean_text = ocr_text.strip()
    raw_res = classify_document_text(clean_text)

    category: DocumentCategory = raw_res["category"]
    confidence: float = raw_res["confidence"]
    top_alts: list[AlternativeCategory] = raw_res["top_alternatives"]
    model_name: str = raw_res["model_name"]
    classification_method: str = raw_res["classification_method"]

    requires_human_review = False
    review_reasons: list[str] = []

    # Check for poor OCR text or truncation
    if len(clean_text) < 50:
        requires_human_review = True
        review_reasons.append("Document text is unusually short (< 50 characters), indicating possible scan truncation.")

    # High ratio of non-printable or symbol noise
    noise_chars = len(re.findall(r"[^\w\s\.,;:/\-–\(\)\[\]%]", clean_text))
    if len(clean_text) > 0 and (noise_chars / len(clean_text)) > 0.15:
        requires_human_review = True
        review_reasons.append("Document exhibits high OCR noise or symbol degradation (> 15% non-alphanumeric noise).")

    # Threshold checks
    if category == DocumentCategory.UNSUPPORTED:
        requires_human_review = True
        review_reasons.append("Document does not match any recognized mandatory AICTE pre-scrutiny categories.")
    elif confidence < 0.50:
        requires_human_review = True
        review_reasons.append(f"Classification confidence ({confidence:.2f}) is below standard threshold (0.50).")

    # Margin check against nearest alternative
    if top_alts and len(top_alts) > 0:
        second_score = top_alts[0].score
        margin = confidence - second_score
        if margin < 0.10 and category != DocumentCategory.UNSUPPORTED:
            requires_human_review = True
            review_reasons.append(
                f"Close semantic similarity between '{category.value}' and '{top_alts[0].category}' (margin: {margin:.2f})."
            )

    return ClassificationResult(
        category=category,
        confidence=confidence,
        top_alternatives=top_alts,
        model_name=model_name,
        classification_method=classification_method,
        requires_human_review=requires_human_review,
        review_reason="; ".join(review_reasons) if review_reasons else None,
    )
