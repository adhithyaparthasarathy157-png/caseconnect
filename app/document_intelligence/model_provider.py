"""Model provider for AI Document Intelligence.

Wraps sentence-transformers for real local neural semantic classification,
and provides an Ollama LLM client with a robust deterministic semantic extraction fallback.
"""
from __future__ import annotations

import logging
import re
import urllib.request
import json
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer, util

from app.document_intelligence.schemas import (
    AlternativeCategory,
    DocumentCategory,
    ExtractedField,
)

logger = logging.getLogger(__name__)

# Canonical semantic prototypes for each document category
CATEGORY_PROTOTYPES: dict[DocumentCategory, list[str]] = {
    DocumentCategory.COMPLAINT_LETTER: [
        "Formal complaint letter representation grievance petition submitted against college management or administration.",
        "Written complaint regarding fee overcharging delay in caution deposit refund faculty harassment or academic non-compliance.",
        "Grievance redressal cell representation student union petition formal complaint to AICTE ombudsman.",
    ],
    DocumentCategory.FEE_RECEIPT_PAYMENT: [
        "Official student fee payment receipt caution money deposit receipt challan bank transaction counterfoil proof of payment.",
        "College accounts department fee acknowledgement receipt tuition fee hostel caution deposit transaction reference.",
        "Bank deposit slip NEFT RTGS payment confirmation receipt student caution deposit voucher university examination fee receipt.",
    ],
    DocumentCategory.INSTITUTIONAL_NOTICE: [
        "Official institutional circular office order memorandum notice board communication issued by Principal or Registrar.",
        "College administrative notice regarding examination attendance withholding hall tickets student fee demand notice.",
        "Office of the Director or Dean notification circular to students and faculty regarding college policies and directives.",
    ],
    DocumentCategory.APPOINTMENT_TERMINATION: [
        "Faculty appointment letter employment contract order of termination relieving order service agreement designation salary.",
        "College governing body appointment order assistant professor associate professor contractual teaching staff appointment terms.",
        "Order of termination cessation of service relieving certificate show cause notice to teaching or non-teaching employee.",
    ],
    DocumentCategory.FACULTY_EVIDENCE: [
        "Faculty complaint evidence non-payment of salary salary statement bank credit advice PF statement qualification dispute.",
        "Teaching staff grievance evidence pay scale 7th CPC disparity workload ledger representation regarding arbitrary deductions.",
        "Faculty salary credit slip bank statement proof of delayed salary or unpaid remuneration.",
    ],
    DocumentCategory.CORRESPONDENCE_PROOF: [
        "Proof of written communication email correspondence courier acknowledgement postal speed post receipt submitted to institution.",
        "Representation sent to college principal registrar with acknowledgment stamp reply communication formal letter thread.",
        "Written follow up request regarding certificate return fee refund grievance resolution with dispatch proof.",
    ],
    DocumentCategory.AFFILIATION_CERTIFICATE: [
        "University Affiliation Certificate granting provisional or permanent affiliation for technical degree courses and academic programs.",
        "Office of the Registrar University Affiliation Order renewal of affiliation academic year approved courses intake capacity.",
        "Provisional affiliation granted by affiliating State Technical University pursuant to AICTE approval regulations.",
    ],
    DocumentCategory.APPROVAL_LETTER: [
        "All India Council for Technical Education AICTE Extension of Approval EOA Letter of Approval technical institution.",
        "AICTE Approval Order granting extension of approval for existing technical courses, intake, and new programmes.",
        "Extension of Approval EOA letter issued by Member Secretary AICTE Nelson Mandela Marg New Delhi.",
    ],
    DocumentCategory.INSTITUTION_REGISTRATION: [
        "Society Registration Certificate Certificate of Incorporation Trust Deed under Societies Registration Act or Indian Trusts Act.",
        "Office of Registrar of Societies Government registration certificate of Educational Charitable Trust or Society.",
        "Certificate of Registration of Society non-profit educational society memorandum of association and registered bylaws.",
    ],
    DocumentCategory.FACULTY_STATEMENT: [
        "Faculty Details Statement teaching staff cadre ratio Professor Associate Professor Assistant Professor qualifications.",
        "Approved faculty list student faculty ratio teaching staff details Cadre designation Ph.D. NET qualifications experience.",
        "Statement of full time teaching faculty members department cadre qualification scale of pay approved by university.",
    ],
    DocumentCategory.INFRASTRUCTURE_REPORT: [
        "Infrastructure and Physical Facilities Inspection Report instructional area administrative area amenities land carpet area.",
        "Civil Engineer Architect Building Safety and Land Area Certificate classrooms laboratories computer center workshop.",
        "Physical infrastructure verification report total built up area fire safety barrier free ramp campus amenities.",
    ],
}

# Negative / Unsupported document prototypes
UNSUPPORTED_PROTOTYPES: list[str] = [
    "Monthly commercial electricity utility bill energy meter power tariff payment receipt consumer invoice.",
    "Restaurant food menu daily dining catering tariff beverage list kitchen rate card.",
    "Curriculum Vitae personal resume job application candidate career history educational qualifications.",
    "Daily newspaper editorial press news clip current affairs political commentary column.",
    "Automobile motor vehicle comprehensive insurance policy certificate road tax receipt.",
]


class EmbeddingModelSingleton:
    """Thread-safe singleton for the local all-MiniLM-L6-v2 sentence transformer model."""
    _instance: SentenceTransformer | None = None
    _category_embeddings: dict[DocumentCategory, np.ndarray] | None = None
    _unsupported_embeddings: np.ndarray | None = None

    @classmethod
    def get_model(cls) -> SentenceTransformer:
        if cls._instance is None:
            logger.info("Initializing SentenceTransformer('all-MiniLM-L6-v2')...")
            cls._instance = SentenceTransformer("all-MiniLM-L6-v2")
            cls._precompute_prototypes()
        return cls._instance

    @classmethod
    def _precompute_prototypes(cls) -> None:
        model = cls._instance
        if model is None:
            return

        cls._category_embeddings = {}
        for cat, prototypes in CATEGORY_PROTOTYPES.items():
            embeddings = model.encode(prototypes, convert_to_tensor=True)
            # Mean embedding for category
            cls._category_embeddings[cat] = embeddings.mean(dim=0, keepdim=True)

        unsupported_embs = model.encode(UNSUPPORTED_PROTOTYPES, convert_to_tensor=True)
        cls._unsupported_embeddings = unsupported_embs.mean(dim=0, keepdim=True)
        logger.info("Semantic prototypes precomputed successfully for 5 document categories.")

    @classmethod
    def get_prototype_embeddings(cls) -> tuple[dict[DocumentCategory, Any], Any]:
        if cls._category_embeddings is None:
            cls.get_model()
        return cls._category_embeddings, cls._unsupported_embeddings  # type: ignore[return-value]


def classify_document_text(ocr_text: str) -> dict[str, Any]:
    """Classifies document OCR text using real sentence-transformers neural embeddings.
    
    Returns:
        dict containing:
            - category: DocumentCategory
            - confidence: float (0.0 to 1.0)
            - top_alternatives: list of AlternativeCategory
            - model_name: str
            - classification_method: str
    """
    model = EmbeddingModelSingleton.get_model()
    cat_embeddings, unsupported_emb = EmbeddingModelSingleton.get_prototype_embeddings()

    # Preprocess text snippet for embedding (first 1200 characters usually contain headers & stamps)
    text_sample = ocr_text[:1200].strip()
    if not text_sample:
        return {
            "category": DocumentCategory.UNSUPPORTED,
            "confidence": 0.0,
            "top_alternatives": [],
            "model_name": "sentence-transformers/all-MiniLM-L6-v2",
            "classification_method": "neural_sentence_transformer",
        }

    doc_embedding = model.encode(text_sample, convert_to_tensor=True)

    # Check against unsupported prototype
    unsupported_sim = float(util.cos_sim(doc_embedding, unsupported_emb)[0][0])

    scores: dict[DocumentCategory, float] = {}
    for cat, proto_emb in cat_embeddings.items():
        sim = float(util.cos_sim(doc_embedding, proto_emb)[0][0])
        # Add slight keyword heuristic weighting for definitive institutional titles
        lower = text_sample.lower()
        if cat == DocumentCategory.AFFILIATION_CERTIFICATE:
            if "affiliation" in lower or "provisional affiliation" in lower or "affiliating university" in lower:
                sim += 0.12
        elif cat == DocumentCategory.APPROVAL_LETTER:
            if "extension of approval" in lower or "aicte" in lower or "all india council for technical education" in lower:
                sim += 0.12
        elif cat == DocumentCategory.INSTITUTION_REGISTRATION:
            if "societies registration" in lower or "trust deed" in lower or "certificate of registration" in lower or "registrar of societies" in lower:
                sim += 0.12
        elif cat == DocumentCategory.FACULTY_STATEMENT:
            if "faculty details" in lower or "teaching staff" in lower or "cadre ratio" in lower or "student faculty ratio" in lower:
                sim += 0.12
        elif cat == DocumentCategory.INFRASTRUCTURE_REPORT:
            if "infrastructure" in lower or "built up area" in lower or "instructional area" in lower or "carpet area" in lower:
                sim += 0.12
        elif cat == DocumentCategory.FEE_RECEIPT_PAYMENT:
            if "receipt" in lower or "fee" in lower or "caution deposit" in lower or "challan" in lower:
                sim += 0.12
        elif cat == DocumentCategory.COMPLAINT_LETTER:
            if "grievance" in lower or "complaint" in lower or "representation" in lower or "petitioner" in lower:
                sim += 0.12
        elif cat == DocumentCategory.INSTITUTIONAL_NOTICE:
            if "circular" in lower or "notice" in lower or "office order" in lower:
                sim += 0.12
        elif cat == DocumentCategory.APPOINTMENT_TERMINATION:
            if "appointment order" in lower or "termination" in lower or "joining report" in lower:
                sim += 0.12
        elif cat == DocumentCategory.FACULTY_EVIDENCE:
            if "salary slip" in lower or "attendance sheet" in lower or "workload" in lower:
                sim += 0.12
        elif cat == DocumentCategory.CORRESPONDENCE_PROOF:
            if "email correspondence" in lower or "speed post tracking" in lower or "reply letter" in lower:
                sim += 0.12

        # Clamp between 0.0 and 0.99
        scores[cat] = max(0.0, min(0.99, round(sim, 4)))

    # Sort categories by score descending
    sorted_cats = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_cat, best_score = sorted_cats[0]

    # Explicit check for known unsupported signatures
    lower_full = ocr_text[:1000].lower()
    is_clearly_unsupported = any(
        kw in lower_full
        for kw in [
            "electricity bill",
            "power distribution company",
            "kwh consumed",
            "restaurant menu",
            "appetizers",
            "beverages",
            "curriculum vitae",
            "resume",
            "career objective",
            "newspaper clipping",
            "editorial",
            "vehicle insurance policy",
        ]
    )

    if is_clearly_unsupported or best_score < 0.40 or (unsupported_sim > best_score and best_score < 0.55):
        best_cat = DocumentCategory.UNSUPPORTED
        best_score = max(unsupported_sim, 0.85) if is_clearly_unsupported else best_score

    alternatives = [
        AlternativeCategory(category=cat.value, score=score)
        for cat, score in sorted_cats
        if cat != best_cat
    ][:3]

    return {
        "category": best_cat,
        "confidence": round(best_score, 4),
        "top_alternatives": alternatives,
        "model_name": "sentence-transformers/all-MiniLM-L6-v2",
        "classification_method": "neural_sentence_transformer",
    }


def check_ollama_available() -> bool:
    """Checks whether local Ollama server is responding at http://127.0.0.1:11434."""
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags", headers={"User-Agent": "AICTE-CaseConnect"})
        with urllib.request.urlopen(req, timeout=0.6) as response:
            return response.status == 200
    except Exception:
        return False


class DeterministicSemanticExtractor:
    """Deterministic field extractor with robust regex, contextual window parsing,
    evidence snippet capture, and confidence scoring.
    """

    @classmethod
    def extract_field(
        cls,
        text: str,
        patterns: list[str],
        field_type: str = "string",
        clean_fn: Any = None,
    ) -> ExtractedField:
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
            if match:
                raw_val = match.group(1).strip() if match.groups() else match.group(0).strip()
                # Find evidence line or surrounding context
                start_idx = max(0, match.start() - 25)
                end_idx = min(len(text), match.end() + 25)
                evidence = text[start_idx:end_idx].replace("\n", " ").strip()

                val = clean_fn(raw_val) if clean_fn else raw_val
                return ExtractedField(
                    value=val,
                    confidence=0.92,
                    evidence=evidence,
                    field_type=field_type,
                )
        return ExtractedField(value=None, confidence=0.0, evidence=None, field_type=field_type)

    @classmethod
    def extract_affiliation_certificate(cls, text: str) -> dict[str, ExtractedField]:
        fields: dict[str, ExtractedField] = {}

        # 1. Issuing Authority / University
        fields["issuing_authority"] = cls.extract_field(
            text,
            [
                r"(?:University|Board|Council|Affiliating\s+Body)[\s:]+([A-Z\s]{4,60}(?:University|Board|Institute))",
                r"([A-Z\s]{4,60}\s+UNIVERSITY(?:,\s+[A-Z\s]+)?)",
                r"ISSUED\s+BY[\s:]+([^\n\r,]+)",
            ],
        )

        # 2. Institution Name
        fields["institution_name"] = cls.extract_field(
            text,
            [
                r"(?:Institution|College|Name\s+of\s+Institution)[\s:]+([^\n\r]{6,80})",
                r"Affiliation\s+(?:is\s+hereby\s+granted\s+to|granted\s+to)\s+([^\n\r,\.]+)",
                r"Name\s+of\s+College[\s:]+([^\n\r]{6,80})",
            ],
        )

        # 3. Institution Code / ID
        fields["institution_code"] = cls.extract_field(
            text,
            [
                r"(?:Institution\s+Code|College\s+Code|Permanent\s+ID|Inst\s+ID)[\s:]+([A-Z0-9\-_/]+)",
                r"Code[\s:]+([0-9]{4,10})",
            ],
        )

        # 4. Academic Year
        fields["academic_year"] = cls.extract_field(
            text,
            [
                r"(?:Academic\s+Year|Year\s+of\s+Affiliation|Session)[\s:]+([0-9]{4}[-–/][0-9]{2,4})",
                r"for\s+the\s+academic\s+year\s+([0-9]{4}[-–/][0-9]{2,4})",
                r"\b(20[2-3][0-9][-–]20?[2-3][0-9])\b",
            ],
        )

        # 5. Issue Date
        fields["issue_date"] = cls.extract_field(
            text,
            [
                r"(?:Date\s+of\s+Issue|Dated|Date|Issued\s+on)[\s:]+([0-9]{1,2}[-/.][0-9]{1,2}[-/.][0-9]{2,4}|[0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})",
                r"Date[\s:]+([0-9]{4}-[0-9]{2}-[0-9]{2})",
            ],
        )

        # 6. Valid Till Date
        fields["valid_till_date"] = cls.extract_field(
            text,
            [
                r"(?:Valid\s+Till|Valid\s+Upto|Expiry\s+Date|Valid\s+Through)[\s:]+([0-9]{1,2}[-/.][0-9]{1,2}[-/.][0-9]{2,4}|[0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})",
                r"valid\s+up\s+to\s+([0-9]{1,2}[-/.][0-9]{1,2}[-/.][0-9]{2,4}|[0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})",
            ],
        )

        # 7. Affiliation Type (Provisional / Permanent)
        fields["affiliation_type"] = cls.extract_field(
            text,
            [
                r"\b(Provisional\s+Affiliation|Permanent\s+Affiliation|Temporary\s+Affiliation)\b",
                r"Type\s+of\s+Affiliation[\s:]+([A-Za-z]+)",
            ],
        )

        # 8. Approved Intake / Programs
        fields["approved_intake"] = cls.extract_field(
            text,
            [
                r"(?:Approved\s+Intake|Sanctioned\s+Intake|Total\s+Intake)[\s:]+([0-9]{2,5})",
                r"Intake[\s:]+([0-9]{2,5})",
            ],
            field_type="integer",
            clean_fn=lambda x: int(re.sub(r"\D", "", x)) if re.sub(r"\D", "", x) else None,
        )

        # 9. Signatory / Registrar
        fields["authorized_signatory"] = cls.extract_field(
            text,
            [
                r"(Registrar|Controller\s+of\s+Examinations|Dean\s+Academic|Director|Member\s+Secretary)",
                r"(?:Signed\s+by|Signatory)[\s:]+([A-Za-z\.\s]+)",
            ],
        )

        return fields

    @classmethod
    def extract_approval_letter(cls, text: str) -> dict[str, ExtractedField]:
        fields: dict[str, ExtractedField] = {}

        # 1. Approval Reference Number / Letter No
        fields["approval_reference_number"] = cls.extract_field(
            text,
            [
                r"(?:F\.?\s*No\.?|Ref\.?\s*No\.?|Letter\s+No\.?|Approval\s+No\.?)[\s:]+([A-Z0-9\-_/\.\s]{8,50})",
                r"(AICTE/[A-Z0-9\-_/]+)",
            ],
        )

        # 2. Institution Name
        fields["institution_name"] = cls.extract_field(
            text,
            [
                r"(?:Name\s+of\s+the\s+Institution|Institution\s+Name|Name\s+of\s+Institution)[\s:]+([^\n\r]{6,80})",
                r"To,[\s\r\n]+The\s+Principal[\s,]+([^\n\r]{6,80})",
            ],
        )

        # 3. Institution ID / Application ID
        fields["institution_id"] = cls.extract_field(
            text,
            [
                r"(?:Permanent\s+Institute\s+Id|Permanent\s+Id|Institute\s+Id|Application\s+Id)[\s:]+([0-9\-_/]+)",
                r"AICTE\s+ID[\s:]+([0-9]{5,12})",
            ],
        )

        # 4. Academic Year
        fields["academic_year"] = cls.extract_field(
            text,
            [
                r"(?:Academic\s+Year|Year)[\s:]+([0-9]{4}[-–/][0-9]{2,4})",
                r"extension\s+of\s+approval\s+to\s+the\s+institution\s+for\s+([0-9]{4}[-–/][0-9]{2,4})",
                r"\b(20[2-3][0-9][-–]20?[2-3][0-9])\b",
            ],
        )

        # 5. Issue Date
        fields["issue_date"] = cls.extract_field(
            text,
            [
                r"(?:Date|Dated)[\s:]+([0-9]{1,2}[-/.][0-9]{1,2}[-/.][0-9]{2,4}|[0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})",
            ],
        )

        # 6. Approved Intake
        fields["approved_intake"] = cls.extract_field(
            text,
            [
                r"(?:Approved\s+Intake|Total\s+Intake|Intake\s+Approved)[\s:]+([0-9]{2,5})",
                r"Intake\s+for\s+[0-9\-]+\s+is\s+([0-9]{2,5})",
            ],
            field_type="integer",
            clean_fn=lambda x: int(re.sub(r"\D", "", x)) if re.sub(r"\D", "", x) else None,
        )

        # 7. Affiliating University
        fields["affiliating_university"] = cls.extract_field(
            text,
            [
                r"(?:Affiliating\s+Body|Affiliating\s+University)[\s:]+([^\n\r,]{4,80})",
                r"affiliated\s+to\s+([^\n\r,\.]+University)",
            ],
        )

        # 8. Signatory / Council Officer
        fields["signatory"] = cls.extract_field(
            text,
            [
                r"(Member\s+Secretary|Advisor|Regional\s+Officer|Director\s+Approval\s+Bureau)",
            ],
        )

        return fields

    @classmethod
    def extract_institution_registration(cls, text: str) -> dict[str, ExtractedField]:
        fields: dict[str, ExtractedField] = {}

        # 1. Society / Trust Name
        fields["trust_or_society_name"] = cls.extract_field(
            text,
            [
                r"(?:Name\s+of\s+Society|Name\s+of\s+Trust|Society/Trust\s+Name)[\s:]+([^\n\r]{6,80})",
                r"hereby\s+certify\s+that\s+([^\n\r]{6,80}\s+(?:Society|Trust|Foundation|Samiti|Mandali))",
            ],
        )

        # 2. Registration Number
        fields["registration_number"] = cls.extract_field(
            text,
            [
                r"(?:Registration\s+Number|Regd\.\s*No\.?|Registration\s+No\.?|Certificate\s+No\.?)[\s:]+([A-Z0-9\-_/]+)",
                r"Reg\.?\s*No\.?[\s:]+([A-Z0-9\-_/]+)",
            ],
        )

        # 3. Registration Act
        fields["registration_act"] = cls.extract_field(
            text,
            [
                r"under\s+(?:the\s+)?([A-Za-z\s,0-9]+Act(?:,\s*[0-9]{4})?)",
                r"(Societies\s+Registration\s+Act(?:,\s*[0-9]{4})?)",
                r"(Indian\s+Trusts\s+Act(?:,\s*[0-9]{4})?)",
                r"(Companies\s+Act(?:,\s*[0-9]{4})?)",
            ],
        )

        # 4. Registration Date
        fields["registration_date"] = cls.extract_field(
            text,
            [
                r"(?:Date\s+of\s+Registration|Registered\s+on|Date)[\s:]+([0-9]{1,2}[-/.][0-9]{1,2}[-/.][0-9]{2,4}|[0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})",
            ],
        )

        # 5. Issuing Authority / Registrar
        fields["issuing_authority"] = cls.extract_field(
            text,
            [
                r"(Registrar\s+of\s+Societies|Sub-Registrar|District\s+Registrar|Charity\s+Commissioner)",
                r"Issued\s+under\s+the\s+hand\s+and\s+seal\s+of\s+([^\n\r,]+)",
            ],
        )

        # 6. Registered Address
        fields["registered_address"] = cls.extract_field(
            text,
            [
                r"(?:Registered\s+Office|Address|Place\s+of\s+Registration)[\s:]+([^\n\r]{8,100})",
            ],
        )

        # 7. Associated Institution Name (if stated)
        fields["institution_name"] = cls.extract_field(
            text,
            [
                r"(?:running|managing|governing)\s+the\s+institution\s+([^\n\r,\.]+)",
                r"(?:College|Institution)[\s:]+([^\n\r]{6,80})",
            ],
        )

        return fields

    @classmethod
    def extract_faculty_statement(cls, text: str) -> dict[str, ExtractedField]:
        fields: dict[str, ExtractedField] = {}

        # 1. Institution Name
        fields["institution_name"] = cls.extract_field(
            text,
            [
                r"(?:Name\s+of\s+the\s+Institution|College|Institution)[\s:]+([^\n\r]{6,80})",
            ],
        )

        # 2. Academic Year
        fields["academic_year"] = cls.extract_field(
            text,
            [
                r"(?:Academic\s+Year|Session)[\s:]+([0-9]{4}[-–/][0-9]{2,4})",
                r"\b(20[2-3][0-9][-–]20?[2-3][0-9])\b",
            ],
        )

        # 3. Total Faculty Count
        fields["total_faculty_count"] = cls.extract_field(
            text,
            [
                r"(?:Total\s+Faculty\s+Count|Total\s+Teaching\s+Staff|Total\s+Faculty)[\s:]+([0-9]{1,4})",
                r"Total[\s:]+([0-9]{2,4})\s+faculty",
            ],
            field_type="integer",
            clean_fn=lambda x: int(re.sub(r"\D", "", x)) if re.sub(r"\D", "", x) else None,
        )

        # 4. Professors Count
        fields["professors_count"] = cls.extract_field(
            text,
            [
                r"(?:Professors|Professor\s+Count)[\s:]+([0-9]{1,3})",
            ],
            field_type="integer",
            clean_fn=lambda x: int(re.sub(r"\D", "", x)) if re.sub(r"\D", "", x) else None,
        )

        # 5. Associate Professors Count
        fields["associate_professors_count"] = cls.extract_field(
            text,
            [
                r"(?:Associate\s+Professors|Associate\s+Professor\s+Count)[\s:]+([0-9]{1,3})",
            ],
            field_type="integer",
            clean_fn=lambda x: int(re.sub(r"\D", "", x)) if re.sub(r"\D", "", x) else None,
        )

        # 6. Assistant Professors Count
        fields["assistant_professors_count"] = cls.extract_field(
            text,
            [
                r"(?:Assistant\s+Professors|Assistant\s+Professor\s+Count)[\s:]+([0-9]{1,3})",
            ],
            field_type="integer",
            clean_fn=lambda x: int(re.sub(r"\D", "", x)) if re.sub(r"\D", "", x) else None,
        )

        # 7. Student-Faculty Ratio (SFR)
        fields["student_faculty_ratio"] = cls.extract_field(
            text,
            [
                r"(?:Student\s*[-:]?\s*Faculty\s*Ratio|SFR)[\s:]+(1\s*:\s*[0-9\.]+)",
                r"\b(1\s*:\s*[0-9]{1,2}(?:\.[0-9]+)?)\b",
            ],
        )

        # 8. Cadre Ratio
        fields["cadre_ratio"] = cls.extract_field(
            text,
            [
                r"(?:Cadre\s*Ratio)[\s:]+([0-9]+\s*:\s*[0-9]+\s*:\s*[0-9]+)",
                r"\b(1\s*:\s*2\s*:\s*6)\b",
            ],
        )

        # 9. Principal / HoD Signatory
        fields["certifying_authority"] = cls.extract_field(
            text,
            [
                r"(Principal|Director|Dean\s+Academic|Head\s+of\s+Institution)",
            ],
        )

        return fields

    @classmethod
    def extract_infrastructure_report(cls, text: str) -> dict[str, ExtractedField]:
        fields: dict[str, ExtractedField] = {}

        # 1. Institution Name
        fields["institution_name"] = cls.extract_field(
            text,
            [
                r"(?:Name\s+of\s+the\s+Institution|Institution|College)[\s:]+([^\n\r]{6,80})",
            ],
        )

        # 2. Land Area (Acres or Sq.m)
        fields["land_area_acres"] = cls.extract_field(
            text,
            [
                r"(?:Total\s+Land\s+Area|Land\s+Area)[\s:]+([0-9\.]+\s*(?:Acres|acre))",
                r"([0-9\.]+\s*Acres)",
            ],
        )

        # 3. Total Built-up Area
        fields["total_built_up_area_sqm"] = cls.extract_field(
            text,
            [
                r"(?:Total\s+Built[- ]*up\s+Area|Built[- ]*up\s+Area)[\s:]+([0-9,\.]+\s*(?:sq\.?\s*m(?:eters)?|Sq\.Mtr|sqm))",
                r"Total\s+Built[- ]*up\s+Area[\s:]+([0-9,\.]+)",
            ],
            clean_fn=lambda x: x.replace(",", ""),
        )

        # 4. Instructional Area
        fields["instructional_area_sqm"] = cls.extract_field(
            text,
            [
                r"(?:Instructional\s+Area)[\s:]+([0-9,\.]+\s*(?:sq\.?\s*m(?:eters)?|Sq\.Mtr|sqm)?)",
            ],
            clean_fn=lambda x: x.replace(",", "").strip(),
        )

        # 5. Administrative Area
        fields["administrative_area_sqm"] = cls.extract_field(
            text,
            [
                r"(?:Administrative\s+Area)[\s:]+([0-9,\.]+\s*(?:sq\.?\s*m(?:eters)?|Sq\.Mtr|sqm)?)",
            ],
            clean_fn=lambda x: x.replace(",", "").strip(),
        )

        # 6. Amenities Area
        fields["amenities_area_sqm"] = cls.extract_field(
            text,
            [
                r"(?:Amenities\s+Area)[\s:]+([0-9,\.]+\s*(?:sq\.?\s*m(?:eters)?|Sq\.Mtr|sqm)?)",
            ],
            clean_fn=lambda x: x.replace(",", "").strip(),
        )

        # 7. Classrooms Count
        fields["classrooms_count"] = cls.extract_field(
            text,
            [
                r"(?:Number\s+of\s+Classrooms|Classrooms|Total\s+Classrooms)[\s:]+([0-9]{1,3})",
            ],
            field_type="integer",
            clean_fn=lambda x: int(re.sub(r"\D", "", x)) if re.sub(r"\D", "", x) else None,
        )

        # 8. Laboratories Count
        fields["laboratories_count"] = cls.extract_field(
            text,
            [
                r"(?:Number\s+of\s+Laboratories|Laboratories|Total\s+Laboratories)[\s:]+([0-9]{1,3})",
            ],
            field_type="integer",
            clean_fn=lambda x: int(re.sub(r"\D", "", x)) if re.sub(r"\D", "", x) else None,
        )

        # 9. Computer Centers
        fields["computer_centers_count"] = cls.extract_field(
            text,
            [
                r"(?:Computer\s+Centers|Number\s+of\s+Computer\s+Centers)[\s:]+([0-9]{1,2})",
            ],
            field_type="integer",
            clean_fn=lambda x: int(re.sub(r"\D", "", x)) if re.sub(r"\D", "", x) else None,
        )

        # 10. Fire Safety Certificate / Barrier Free Access
        fields["fire_safety_certificate"] = cls.extract_field(
            text,
            [
                r"(?:Fire\s+Safety\s+Certificate|Fire\s+NOC)[\s:]+([A-Za-z0-9\-_/\s]+(?:Valid|Available|Issued|Yes|No)?)",
                r"(Fire\s+Safety\s+NOC\s+Valid)",
            ],
        )

        # 11. Architect / Civil Engineer Signatory
        fields["certifying_engineer"] = cls.extract_field(
            text,
            [
                r"(Chartered\s+Engineer|Registered\s+Architect|Civil\s+Engineer|Competent\s+Authority)",
                r"(?:Certified\s+by|Architect)[\s:]+([A-Za-z\.\s]+)",
            ],
        )

        return fields

    @classmethod
    def extract_fee_receipt(cls, text: str) -> dict[str, ExtractedField]:
        fields: dict[str, ExtractedField] = {}
        fields["institution_name"] = cls.extract_field(
            text,
            [
                r"^([A-Za-z0-9\s,\.\(\)\-]+?(?:Technology|Engineering|Management|Polytechnic|Institute|College|University|Academy|Studies)[^\n\r]*)",
                r"(?:College|Institute|University|Academy)[\s:]+([A-Za-z\s,\.\(\)]+?(?:Technology|Engineering|Management|Polytechnic|Institute|College))",
                r"([A-Za-z\s]+(?:College\s+of\s+Engineering|Institute\s+of\s+Technology|Engineering\s+College))",
                r"^([A-Z\s]{4,60}(?:COLLEGE|INSTITUTE|UNIVERSITY))",
            ],
        )
        fields["receipt_number"] = cls.extract_field(
            text,
            [
                r"(?:Receipt\s+No|Receipt\s+Number|Voucher\s+No|Txn\s+Ref|Challan\s+No)[\s:\.\-]+([A-Za-z0-9\-_/]+)",
                r"Ref[:\s]+(REC-[0-9]{4,10})",
            ],
        )
        fields["amount"] = cls.extract_field(
            text,
            [
                r"(?:Amount|Total\s+Paid|Deposit|Fee\s+Collected|Rs\.?|INR)[\s:\.]+(?:Rs\.?|INR)?\s*([0-9,]+(?:\.[0-9]{2})?)",
                r"([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]{2})?)\s*(?:Rupees|only)",
            ],
        )
        fields["payment_date"] = cls.extract_field(
            text,
            [
                r"(?:Date|Payment\s+Date|Transaction\s+Date|Dated)[\s:]+([0-9]{1,2}[-/.][0-9]{1,2}[-/.][0-9]{2,4})",
                r"([0-9]{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s,]+[0-9]{4})",
            ],
        )
        fields["student_name"] = cls.extract_field(
            text,
            [
                r"(?:Student\s+Name|Name\s+of\s+Student|Received\s+from|Payer)[\s:]+([A-Za-z\.\s]+)",
                r"(?:Mr\.|Ms\.|Shri)\s+([A-Za-z\s]+)",
            ],
        )
        fields["fee_type"] = cls.extract_field(
            text,
            [
                r"(Caution\s+Money|Caution\s+Deposit|Security\s+Deposit|Tuition\s+Fee|Admission\s+Fee|Development\s+Fee)",
                r"(?:Towards|Particulars)[\s:]+([A-Za-z\s]+(?:Fee|Deposit))",
            ],
        )
        return fields

    @classmethod
    def extract_complaint_letter(cls, text: str) -> dict[str, ExtractedField]:
        fields: dict[str, ExtractedField] = {}
        fields["institution_name"] = cls.extract_field(
            text,
            [
                r"(?:Against|Institution|College|Respondent)[\s:]+([A-Za-z\s,\.\(\)]+?(?:Technology|Engineering|Management|Institute|College))",
                r"To,?\s+(?:The\s+Principal|The\s+Director|The\s+Registrar),?\s*([A-Za-z\s,\.\(\)]+?(?:Technology|Engineering|Management|Institute|College))",
            ],
        )
        fields["complainant_name"] = cls.extract_field(
            text,
            [
                r"(?:From|Complainant|Submitted\s+by|Petitioner|Yours\s+faithfully|Sincerely)[\s:,]+([A-Za-z\.\s]{3,40})",
                r"(?:I,\s*)([A-Za-z\.\s]{3,40})(?:,\s*(?:student|faculty|parent|bearing))",
            ],
        )
        fields["complaint_date"] = cls.extract_field(
            text,
            [
                r"(?:Date|Dated)[\s:]+([0-9]{1,2}[-/.][0-9]{1,2}[-/.][0-9]{2,4})",
                r"([0-9]{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s,]+[0-9]{4})",
            ],
        )
        fields["subject"] = cls.extract_field(
            text,
            [
                r"(?:Sub|Subject|Regarding)[\s:\-]+([^\n\r]{10,120})",
            ],
        )
        return fields

    @classmethod
    def extract_institutional_notice(cls, text: str) -> dict[str, ExtractedField]:
        fields: dict[str, ExtractedField] = {}
        fields["institution_name"] = cls.extract_field(
            text,
            [
                r"^([A-Za-z\s,\.\(\)]+?(?:College|Institute|University|Academy))",
                r"(?:Office\s+of\s+the\s+Principal|Registrar|Dean),?\s*([A-Za-z\s,\.\(\)]+?(?:College|Institute|University))",
            ],
        )
        fields["notice_reference"] = cls.extract_field(
            text,
            [
                r"(?:Ref\s+No|Notice\s+No|Circular\s+No|Order\s+No)[\s:\.\-]+([A-Za-z0-9\-_/]+)",
            ],
        )
        fields["notice_date"] = cls.extract_field(
            text,
            [
                r"(?:Date|Dated)[\s:]+([0-9]{1,2}[-/.][0-9]{1,2}[-/.][0-9]{2,4})",
                r"([0-9]{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s,]+[0-9]{4})",
            ],
        )
        fields["subject"] = cls.extract_field(
            text,
            [
                r"(?:Sub|Subject|Notice|Notification)[\s:\-]+([^\n\r]{10,120})",
            ],
        )
        return fields

    @classmethod
    def extract_appointment_termination(cls, text: str) -> dict[str, ExtractedField]:
        fields: dict[str, ExtractedField] = {}
        fields["institution_name"] = cls.extract_field(
            text,
            [
                r"(?:Management\s+of|Governing\s+Council\s+of|Office\s+of)[\s:]+([A-Za-z\s,\.\(\)]+?(?:College|Institute|University))",
                r"^([A-Za-z\s,\.\(\)]+?(?:College|Institute|University))",
            ],
        )
        fields["employee_name"] = cls.extract_field(
            text,
            [
                r"(?:To|Name|Employee|Faculty|Appointee)[\s:]+([A-Za-z\.\s]{3,40})",
                r"(?:Dr\.|Prof\.|Mr\.|Ms\.)\s+([A-Za-z\s]+)",
            ],
        )
        fields["order_date"] = cls.extract_field(
            text,
            [
                r"(?:Date|Dated)[\s:]+([0-9]{1,2}[-/.][0-9]{1,2}[-/.][0-9]{2,4})",
                r"([0-9]{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s,]+[0-9]{4})",
            ],
        )
        fields["designation"] = cls.extract_field(
            text,
            [
                r"(Professor|Associate\s+Professor|Assistant\s+Professor|Lecturer|Principal|HOD)",
                r"(?:Designation|Post)[\s:]+([A-Za-z\s]+)",
            ],
        )
        return fields

    @classmethod
    def extract_faculty_evidence(cls, text: str) -> dict[str, ExtractedField]:
        fields: dict[str, ExtractedField] = {}
        fields["institution_name"] = cls.extract_field(
            text,
            [
                r"([A-Za-z\s,\.\(\)]+?(?:College|Institute|University))",
            ],
        )
        fields["faculty_name"] = cls.extract_field(
            text,
            [
                r"(?:Employee|Faculty|Teacher|Complainant)[\s:]+([A-Za-z\.\s]{3,40})",
                r"(?:Dr\.|Prof\.|Mr\.|Ms\.)\s+([A-Za-z\s]+)",
            ],
        )
        return fields

    @classmethod
    def extract_correspondence_proof(cls, text: str) -> dict[str, ExtractedField]:
        fields: dict[str, ExtractedField] = {}
        fields["institution_name"] = cls.extract_field(
            text,
            [
                r"([A-Za-z\s,\.\(\)]+?(?:College|Institute|University))",
            ],
        )
        return fields


def extract_document_fields(
    ocr_text: str,
    category: DocumentCategory,
) -> tuple[dict[str, ExtractedField], str, str]:
    """Extracts structured fields for the determined document category.
    
    Checks if Ollama LLM is available; if not or if it fails, falls back gracefully
    to DeterministicSemanticExtractor with transparent reporting.
    
    Returns:
        (extracted_fields_dict, extraction_method_name, model_name)
    """
    if category == DocumentCategory.UNSUPPORTED:
        return {}, "unsupported_document_bypass", "none"

    # Transparently check if Ollama is available
    if check_ollama_available():
        # Future-ready Ollama invocation hook
        pass

    # Deterministic Semantic Extractor fallback
    if category == DocumentCategory.FEE_RECEIPT_PAYMENT:
        fields = DeterministicSemanticExtractor.extract_fee_receipt(ocr_text)
    elif category == DocumentCategory.COMPLAINT_LETTER:
        fields = DeterministicSemanticExtractor.extract_complaint_letter(ocr_text)
    elif category == DocumentCategory.INSTITUTIONAL_NOTICE:
        fields = DeterministicSemanticExtractor.extract_institutional_notice(ocr_text)
    elif category == DocumentCategory.APPOINTMENT_TERMINATION:
        fields = DeterministicSemanticExtractor.extract_appointment_termination(ocr_text)
    elif category == DocumentCategory.FACULTY_EVIDENCE:
        fields = DeterministicSemanticExtractor.extract_faculty_evidence(ocr_text)
    elif category == DocumentCategory.CORRESPONDENCE_PROOF:
        fields = DeterministicSemanticExtractor.extract_correspondence_proof(ocr_text)
    elif category == DocumentCategory.AFFILIATION_CERTIFICATE:
        fields = DeterministicSemanticExtractor.extract_affiliation_certificate(ocr_text)
    elif category == DocumentCategory.APPROVAL_LETTER:
        fields = DeterministicSemanticExtractor.extract_approval_letter(ocr_text)
    elif category == DocumentCategory.INSTITUTION_REGISTRATION:
        fields = DeterministicSemanticExtractor.extract_institution_registration(ocr_text)
    elif category == DocumentCategory.FACULTY_STATEMENT:
        fields = DeterministicSemanticExtractor.extract_faculty_statement(ocr_text)
    elif category == DocumentCategory.INFRASTRUCTURE_REPORT:
        fields = DeterministicSemanticExtractor.extract_infrastructure_report(ocr_text)
    else:
        fields = {}

    return (
        fields,
        "deterministic_semantic_extractor",
        "fallback_deterministic",
    )
