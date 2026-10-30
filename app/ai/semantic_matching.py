"""
Semantic case matching service.
Enhances existing SequenceMatcher overlap scoring with sentence-transformers.
Reuses EmbeddingModelSingleton from document_intelligence package.
"""
from __future__ import annotations

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.document_intelligence.model_provider import EmbeddingModelSingleton
from app.models import Case, OverlapCandidate


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / norm) if norm > 0 else 0.0


def get_semantic_matches(case: Case, db: Session, top_k: int = 5) -> list[dict]:
    """
    Return semantically similar cases for a given case using sentence-transformers.
    Only considers cases from the same institution (consistent with existing overlap logic).
    Potential matches are NEVER automatically merged or rejected; human officer review required.
    """
    same_institution_cases = db.scalars(
        select(Case).where(
            Case.institution_id == case.institution_id,
            Case.id != case.id,
        )
    ).all()

    if not same_institution_cases:
        return []

    try:
        model = EmbeddingModelSingleton.get()
        query_text = f"{case.subject} {case.description}"
        query_vec = model.encode([query_text])[0]

        results = []
        for other in same_institution_cases:
            other_text = f"{other.subject} {other.description}"
            other_vec = model.encode([other_text])[0]
            sim = _cosine_sim(query_vec, other_vec)
            if sim >= 0.35:  # Sensitive enough to catch different wordings with similar meanings
                # Check if overlap exists
                low_id, high_id = sorted([case.id, other.id])
                existing_overlap = db.scalar(
                    select(OverlapCandidate).where(
                        OverlapCandidate.case_low_id == low_id,
                        OverlapCandidate.case_high_id == high_id,
                    )
                )

                is_cross = case.current_bureau_id != other.current_bureau_id
                this_bureau_code = case.current_bureau.code if case.current_bureau else f"Bureau #{case.current_bureau_id}"
                other_bureau_code = other.current_bureau.code if other.current_bureau else f"Bureau #{other.current_bureau_id}"
                inst_name = other.institution.name if other.institution else f"Institution #{other.institution_id}"

                if is_cross:
                    coordination_action = (
                        f"Cross-Bureau Overlap detected between {this_bureau_code} and {other_bureau_code}. "
                        "Recommend initiating formal bilateral coordination request. Do NOT automatically merge or close."
                    )
                else:
                    coordination_action = (
                        f"Intra-Bureau Overlap: Both cases assigned to {this_bureau_code}. "
                        "Recommend reviewing case context for linked processing. Retain independent case lifecycles."
                    )

                explanation = (
                    f"Complaints both relate to '{other.category}' for {inst_name}. "
                    f"Sentence-transformers semantic similarity of {round(sim * 100, 1)}% indicates shared factual substance "
                    "despite distinct complaint wording. Preserves individual case dockets; human confirmation mandatory."
                )

                results.append({
                    "case_id": other.case_id,
                    "target_case_numeric_id": other.id,
                    "institution_id": other.institution_id,
                    "institution_name": inst_name,
                    "permanent_id": other.institution.permanent_id if other.institution else None,
                    "subject": other.subject,
                    "category": other.category,
                    "status": other.status,
                    "semantic_similarity": round(sim, 4),
                    "similarity_percent": round(sim * 100, 1),
                    "interpretation": (
                        "Near-duplicate" if sim >= 0.88
                        else "Highly related" if sim >= 0.70
                        else "Related" if sim >= 0.50
                        else "Possibly related"
                    ),
                    "matching_explanation": explanation,
                    "this_bureau_code": this_bureau_code,
                    "target_bureau_code": other_bureau_code,
                    "is_cross_bureau": is_cross,
                    "recommended_coordination_action": coordination_action,
                    "overlap_exists": existing_overlap is not None,
                    "overlap_id": existing_overlap.id if existing_overlap else None,
                    "overlap_status": existing_overlap.status if existing_overlap else None,
                    "model": "all-MiniLM-L6-v2 (sentence-transformers)",
                    "method": "neural_cosine_semantic_similarity",
                    "auto_merged": False,
                })
        return sorted(results, key=lambda x: x["semantic_similarity"], reverse=True)[:top_k]
    except Exception as exc:
        return [{"error": f"Semantic matching unavailable: {exc}", "fallback": "Use existing overlap engine"}]


def compute_enhanced_overlap_score(left: Case, right: Case) -> tuple[float, list[str]]:
    """
    Compute semantic similarity between two cases.
    Returns (similarity_score_0_to_1, list_of_evidence_snippets).
    For use as an enhancement to existing SequenceMatcher score.
    """
    try:
        model = EmbeddingModelSingleton.get()
        left_text = f"{left.subject} {left.description}"
        right_text = f"{right.subject} {right.description}"
        vecs = model.encode([left_text, right_text])
        sim = _cosine_sim(vecs[0], vecs[1])
        evidence = []
        if sim >= 0.80:
            evidence.append(f"Semantic similarity: {round(sim * 100)}% (high)")
        elif sim >= 0.60:
            evidence.append(f"Semantic similarity: {round(sim * 100)}% (moderate)")
        elif sim >= 0.40:
            evidence.append(f"Semantic similarity: {round(sim * 100)}% (low)")
        return sim, evidence
    except Exception:
        return 0.0, []

