"""Synthetic OCR Document Library for AICTE Document Intelligence & Pre-Scrutiny.

Contains 39 comprehensive, realistic, and internally consistent synthetic OCR fixtures
spanning all 5 regulatory document categories, 7 distinct pre-scrutiny scenarios,
unsupported control documents, and degraded OCR test cases.
"""
from __future__ import annotations

from typing import Any

from app.document_intelligence.schemas import (
    DocumentCategory,
    PreScrutinyStatus,
)

SYNTHETIC_FIXTURES: list[dict[str, Any]] = [
    # =========================================================================
    # CATEGORY 1: AFFILIATION CERTIFICATE
    # =========================================================================
    {
        "fixture_id": "SYN-AFF-01-VALID",
        "category": DocumentCategory.AFFILIATION_CERTIFICATE,
        "scenario": "VALID DOCUMENT",
        "is_demo_scenario": True,
        "demo_title": "Demo 1: Valid Affiliation Certificate",
        "institution_name": "Fictional North Institute of Technology 01",
        "institution_identifier": "DEMO-AICTE-0001",
        "associated_case_id": "CC-2026-00001",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.AFFILIATION_CERTIFICATE.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.PASSED.value,
        "expected_recommended_action": "Document satisfies all mandatory AICTE pre-scrutiny criteria and institution registry alignment.",
        "description": "Clean, fully compliant provisional affiliation certificate issued by affiliating technical university for Academic Year 2024-25 with all required fields present.",
        "ocr_text": """STATE TECHNICAL UNIVERSITY OF THE NORTH
OFFICE OF THE REGISTRAR, AFFILIATION & ACCREDITATION DIVISION
Administrative Block, University Campus, Sector 14, City Centre - 110001

PROVISIONAL AFFILIATION NOTIFICATION / CERTIFICATE
Order Ref. No.: STU/AFF/2024-25/TECH-0982
Dated: 22 May 2024

Subject: Grant of Provisional Affiliation for Academic Year 2024-25 - Regarding.

In exercise of the powers conferred under Section 24 of the State Technical Universities Act and in accordance with the regulatory norms prescribed by the All India Council for Technical Education (AICTE), provisional affiliation is hereby granted to:

Institution: Fictional North Institute of Technology 01
Institution Code: DEMO-AICTE-0001
Permanent ID: DEMO-AICTE-0001

for conducting the following undergraduate & postgraduate engineering programmes for the Academic Year: 2024-25:

1. B.Tech Computer Science and Engineering - Approved Intake: 180
2. B.Tech Electronics and Communication Engineering - Approved Intake: 120
3. B.Tech Mechanical Engineering - Approved Intake: 60
4. M.Tech Artificial Intelligence and Data Science - Approved Intake: 24

Total Approved Intake: 384 seats.
Type of Affiliation: Provisional Affiliation
Validity Period: Valid Till 30-06-2025

Conditions:
1. The institution shall adhere strictly to the rules and regulations framed by AICTE and State Technical University.
2. The sanctioned intake shall not be exceeded under any circumstances without prior university approval.

Issued under the seal of the University.

Sd/-
Registrar
State Technical University
(Authorized Signatory)""",
    },
    {
        "fixture_id": "SYN-AFF-02-MISSING",
        "category": DocumentCategory.AFFILIATION_CERTIFICATE,
        "scenario": "MISSING INFORMATION",
        "is_demo_scenario": False,
        "institution_name": "Fictional North Institute of Technology 01",
        "institution_identifier": "DEMO-AICTE-0001",
        "associated_case_id": "CC-2026-00001",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.AFFILIATION_CERTIFICATE.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.FLAGGED.value,
        "expected_recommended_action": "Scrutiny officer should review findings and dispatch formal deficiency notice to the institution.",
        "description": "Affiliation order missing authorized signatory and institution code.",
        "ocr_text": """STATE TECHNICAL UNIVERSITY OF THE NORTH
OFFICE OF THE REGISTRAR
AFFILIATION MEMORANDUM (DRAFT COPY)

Order Ref: STU/AFF/TEMP/2024-99
Date: 15 June 2024

Grant of Affiliation for Academic Year 2024-25:
Affiliation granted to Fictional North Institute of Technology 01 for B.Tech degrees.
Total Approved Intake: 300

[DOCUMENT CUTS OFF HERE - SIGNATURE AND REGISTRAR STAMP OMITTED]
[NO INSTITUTION CODE SPECIFIED]""",
    },
    {
        "fixture_id": "SYN-AFF-03-EXPIRED",
        "category": DocumentCategory.AFFILIATION_CERTIFICATE,
        "scenario": "INVALID OR EXPIRED INFORMATION",
        "is_demo_scenario": True,
        "demo_title": "Demo 2: Expired Affiliation Certificate",
        "institution_name": "Fictional North Institute of Technology 01",
        "institution_identifier": "DEMO-AICTE-0001",
        "associated_case_id": "CC-2026-00001",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.AFFILIATION_CERTIFICATE.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.FLAGGED.value,
        "expected_recommended_action": "Scrutiny officer should review findings and dispatch formal deficiency notice to the institution.",
        "description": "Affiliation certificate with expired validity date (lapsed 30 June 2022, academic year 2021-22).",
        "ocr_text": """STATE TECHNICAL UNIVERSITY OF THE NORTH
OFFICE OF THE REGISTRAR

ANNUAL AFFILIATION CERTIFICATE
Order Ref: STU/AFF/2021-22/HIST-004
Date of Issue: 14 July 2021

This is to certify that provisional affiliation was accorded to:
Institution: Fictional North Institute of Technology 01
Institution Code: DEMO-AICTE-0001
Academic Year: 2021-22

Approved Courses:
- B.Tech Computer Science: 120 seats
- B.Tech Information Technology: 60 seats

Expiry Date / Valid Till: 30/06/2022
Type of Affiliation: Provisional Affiliation

Notice: This provisional order shall cease to have effect post 30 June 2022 unless explicitly renewed.

Sd/-
Registrar
State Technical University""",
    },
    {
        "fixture_id": "SYN-AFF-04-MISMATCH",
        "category": DocumentCategory.AFFILIATION_CERTIFICATE,
        "scenario": "INSTITUTION MISMATCH",
        "is_demo_scenario": False,
        "institution_name": "Fictional North Institute of Technology 01",
        "institution_identifier": "DEMO-AICTE-0001",
        "associated_case_id": "CC-2026-00001",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.AFFILIATION_CERTIFICATE.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.FLAGGED.value,
        "expected_recommended_action": "Scrutiny officer should review findings and dispatch formal deficiency notice to the institution.",
        "description": "Certificate issued for 'Sunrise Valley College of Engineering' uploaded under Case CC-2026-00001.",
        "ocr_text": """STATE TECHNICAL UNIVERSITY OF THE NORTH
OFFICE OF THE REGISTRAR

PROVISIONAL AFFILIATION ORDER
Order No: STU/AFF/2024-25/ERR-441
Date: 18 June 2024

Subject: Affiliation for Academic Year 2024-25.

Provisional affiliation is hereby granted to:
Institution: Sunrise Valley College of Engineering and Technology
Institution Code: DEMO-OTHER-8899

for conducting technical engineering programmes for Academic Year: 2024-25.
Approved Intake: 360
Valid Till: 30-06-2025

Sd/-
Registrar
State Technical University""",
    },
    {
        "fixture_id": "SYN-AFF-05-INCONSISTENT",
        "category": DocumentCategory.AFFILIATION_CERTIFICATE,
        "scenario": "INCONSISTENT INFORMATION",
        "is_demo_scenario": False,
        "institution_name": "Fictional North Institute of Technology 01",
        "institution_identifier": "DEMO-AICTE-0001",
        "associated_case_id": "CC-2026-00001",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.AFFILIATION_CERTIFICATE.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.FLAGGED.value,
        "expected_recommended_action": "Scrutiny officer should review findings and dispatch formal deficiency notice to the institution.",
        "description": "Header claims Academic Year 2024-25 but body condition stipulates Provisional affiliation for 2023-24 only.",
        "ocr_text": """STATE TECHNICAL UNIVERSITY OF THE NORTH
OFFICE OF THE REGISTRAR

RENEWAL OF AFFILIATION ORDER
Order Ref: STU/AFF/2024-25/INC-109
Date of Issue: 10 May 2024

Affiliation Order for Academic Year: 2024-25
Institution: Fictional North Institute of Technology 01
Institution Code: DEMO-AICTE-0001

The Syndicate of the University is pleased to grant affiliation.
Special Condition:
Provisional affiliation for 2023-24 only. The college must submit compliance report by August 2023.

Approved Intake: 240
Type: Provisional Affiliation

Sd/-
Registrar
State Technical University""",
    },
    {
        "fixture_id": "SYN-AFF-06-CORRECTED",
        "category": DocumentCategory.AFFILIATION_CERTIFICATE,
        "scenario": "CORRECTED DOCUMENT",
        "is_demo_scenario": False,
        "institution_name": "Fictional North Institute of Technology 01",
        "institution_identifier": "DEMO-AICTE-0001",
        "associated_case_id": "CC-2026-00001",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.AFFILIATION_CERTIFICATE.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.PASSED.value,
        "expected_recommended_action": "Document satisfies all mandatory AICTE pre-scrutiny criteria and institution registry alignment.",
        "description": "Corrected and endorsed affiliation order resolving previous validity and signature discrepancies.",
        "ocr_text": """STATE TECHNICAL UNIVERSITY OF THE NORTH
OFFICE OF THE REGISTRAR, AFFILIATION BUREAU
University Campus, Sector 14, City Centre - 110001

CORRIGENDUM & PROVISIONAL AFFILIATION ORDER (AMENDED)
Order Ref. No.: STU/AFF/2024-25/TECH-0982-CORR
Date: 12 July 2024

In supersession of previous provisional order, full provisional affiliation is confirmed for:
Institution: Fictional North Institute of Technology 01
Institution Code: DEMO-AICTE-0001
Permanent ID: DEMO-AICTE-0001

Academic Year: 2024-25
Valid Till: 30-06-2025
Approved Intake: 384
Type of Affiliation: Provisional Affiliation

All compliance observations for 2024-25 have been satisfied and reconciled with AICTE norms.

Sd/-
Registrar
State Technical University
(Authorized Signatory)""",
    },
    {
        "fixture_id": "SYN-AFF-07-POOR-OCR",
        "category": DocumentCategory.AFFILIATION_CERTIFICATE,
        "scenario": "POOR OCR INPUT",
        "is_demo_scenario": False,
        "institution_name": "Fictional North Institute of Technology 01",
        "institution_identifier": "DEMO-AICTE-0001",
        "associated_case_id": "CC-2026-00001",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.AFFILIATION_CERTIFICATE.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.NEEDS_HUMAN_REVIEW.value,
        "expected_recommended_action": "No outright rule violations detected, but text clarity or confidence warrants officer manual review before acceptance.",
        "description": "Degraded OCR scan with speckles and noisy character replacement requiring human officer confirmation.",
        "ocr_text": """ST@TE T3CHN1CAL UN1V3RS1TY 0F TH3 N0RTH
0FF1C3 0F TH3 R3G1STR@R
0rd3r R3f: STU/AFF/2O24-25/###
D@t3: 2024

PR0V1S10N@L AFF1L1AT10N C3RT1F1C@T3
Inst: Fictional North Institute of Technology 01
C0de: DEMO-AICTE-0001
Acad3mic Y3ar: 2024-25
Int@k3: 384
V@lid Upto: 30/06/2025

Sd/-
R3g1str@r""",
    },

    # =========================================================================
    # CATEGORY 2: APPROVAL LETTER (AICTE EOA)
    # =========================================================================
    {
        "fixture_id": "SYN-APP-01-VALID",
        "category": DocumentCategory.APPROVAL_LETTER,
        "scenario": "VALID DOCUMENT",
        "is_demo_scenario": False,
        "institution_name": "Fictional South Institute of Technology 02",
        "institution_identifier": "DEMO-AICTE-0002",
        "associated_case_id": "CC-2026-00002",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.APPROVAL_LETTER.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.PASSED.value,
        "expected_recommended_action": "Document satisfies all mandatory AICTE pre-scrutiny criteria and institution registry alignment.",
        "description": "Official AICTE Extension of Approval (EOA) letter for Academic Year 2024-25 with all mandatory parameters verified.",
        "ocr_text": """ALL INDIA COUNCIL FOR TECHNICAL EDUCATION
(A Statutory Body under Ministry of Education, Govt. of India)
Nelson Mandela Marg, Vasant Kunj, New Delhi-110070
Website: www.aicte-india.org

APPROVAL PROCESS 2024-25
Extension of Approval (EOA)
F.No. South/1-9318281029/2024/EOA
Date: 30-Apr-2024

To,
The Principal,
Fictional South Institute of Technology 02,
Tech Campus Road, Sector 8, Southern Hub - 600001

Sub: Extension of Approval for the Academic Year 2024-25
Ref: Application of the Institution for Extension of Approval for the Academic Year 2024-25

Sir/Madam,
In terms of the provisions under the All India Council for Technical Education (Grant of Approvals for Technical Institutions) Regulations, 2020 and subsequent amendments, I am directed to convey the approval to:

Permanent Institute Id: DEMO-AICTE-0002
Application Id: 1-9318281029
Name of the Institution: Fictional South Institute of Technology 02
Affiliating University: State Technical University
Academic Year: 2024-25

Approved Courses & Intake:
- Civil Engineering (UG): 60
- Computer Science and Engineering (UG): 180
- Electrical and Electronics Engineering (UG): 60
Approved Intake: 300

The Institution shall strictly comply with all mandatory safety norms and cadre ratios.

Prof. Rajive Kumar
Member Secretary, AICTE""",
    },
    {
        "fixture_id": "SYN-APP-02-MISSING",
        "category": DocumentCategory.APPROVAL_LETTER,
        "scenario": "MISSING INFORMATION",
        "is_demo_scenario": False,
        "institution_name": "Fictional South Institute of Technology 02",
        "institution_identifier": "DEMO-AICTE-0002",
        "associated_case_id": "CC-2026-00002",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.APPROVAL_LETTER.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.FLAGGED.value,
        "expected_recommended_action": "Scrutiny officer should review findings and dispatch formal deficiency notice to the institution.",
        "description": "Approval letter missing Permanent Institute ID and dispatch reference number.",
        "ocr_text": """ALL INDIA COUNCIL FOR TECHNICAL EDUCATION
Nelson Mandela Marg, Vasant Kunj, New Delhi-110070

EXTENSION OF APPROVAL ORDER
Date: 15-May-2024

To,
The Principal,
Fictional South Institute of Technology 02

Sub: Extension of approval for Academic Year 2024-25.
Approval is granted for undergraduate engineering programmes for 2024-25.
Approved Intake: 300

Sd/-
Regional Officer, AICTE""",
    },
    {
        "fixture_id": "SYN-APP-03-EXPIRED",
        "category": DocumentCategory.APPROVAL_LETTER,
        "scenario": "INVALID OR EXPIRED INFORMATION",
        "is_demo_scenario": False,
        "institution_name": "Fictional South Institute of Technology 02",
        "institution_identifier": "DEMO-AICTE-0002",
        "associated_case_id": "CC-2026-00002",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.APPROVAL_LETTER.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.FLAGGED.value,
        "expected_recommended_action": "Scrutiny officer should review findings and dispatch formal deficiency notice to the institution.",
        "description": "Approval letter valid only for prior academic year 2022-23.",
        "ocr_text": """ALL INDIA COUNCIL FOR TECHNICAL EDUCATION
Nelson Mandela Marg, Vasant Kunj, New Delhi-110070

APPROVAL PROCESS 2022-23
Extension of Approval (EOA)
F.No. South/1-7261524311/2022/EOA
Date: 02-Jun-2022

To,
The Principal,
Fictional South Institute of Technology 02

Sub: Extension of Approval for the Academic Year 2022-23
Permanent Institute Id: DEMO-AICTE-0002
Academic Year: 2022-23
Approved Intake: 300

Member Secretary, AICTE""",
    },
    {
        "fixture_id": "SYN-APP-04-MISMATCH",
        "category": DocumentCategory.APPROVAL_LETTER,
        "scenario": "INSTITUTION MISMATCH",
        "is_demo_scenario": True,
        "demo_title": "Demo 3: Institution Mismatch in Approval Letter",
        "institution_name": "Fictional North Institute of Technology 01",
        "institution_identifier": "DEMO-AICTE-0001",
        "associated_case_id": "CC-2026-00001",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.APPROVAL_LETTER.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.FLAGGED.value,
        "expected_recommended_action": "Scrutiny officer should review findings and dispatch formal deficiency notice to the institution.",
        "description": "Approval letter for 'Eastern Royal College of Technology' uploaded into Case CC-2026-00001.",
        "ocr_text": """ALL INDIA COUNCIL FOR TECHNICAL EDUCATION
Nelson Mandela Marg, Vasant Kunj, New Delhi-110070

APPROVAL PROCESS 2024-25
Extension of Approval (EOA)
F.No. East/1-9988776655/2024/EOA
Date: 25-Apr-2024

To,
The Principal,
Eastern Royal College of Technology,
Plot 44, Industrial Area, East Zone - 700001

Sub: Extension of Approval for Academic Year 2024-25
Permanent Institute Id: DEMO-AICTE-9999
Name of the Institution: Eastern Royal College of Technology
Academic Year: 2024-25
Approved Intake: 420

Member Secretary, AICTE""",
    },
    {
        "fixture_id": "SYN-APP-05-INCONSISTENT",
        "category": DocumentCategory.APPROVAL_LETTER,
        "scenario": "INCONSISTENT INFORMATION",
        "is_demo_scenario": False,
        "institution_name": "Fictional South Institute of Technology 02",
        "institution_identifier": "DEMO-AICTE-0002",
        "associated_case_id": "CC-2026-00002",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.APPROVAL_LETTER.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.FLAGGED.value,
        "expected_recommended_action": "Scrutiny officer should review findings and dispatch formal deficiency notice to the institution.",
        "description": "Approval letter citing mismatched permanent ID and conflicting intake.",
        "ocr_text": """ALL INDIA COUNCIL FOR TECHNICAL EDUCATION
Nelson Mandela Marg, Vasant Kunj, New Delhi-110070

APPROVAL PROCESS 2024-25
Extension of Approval (EOA)
F.No. South/1-9318281029/2024/EOA
Date: 28-Apr-2024

Name of the Institution: Fictional South Institute of Technology 02
Permanent Institute Id: 1-9999999999
Academic Year: 2024-25
Approved Intake: 600

Member Secretary, AICTE""",
    },
    {
        "fixture_id": "SYN-APP-06-CORRECTED",
        "category": DocumentCategory.APPROVAL_LETTER,
        "scenario": "CORRECTED DOCUMENT",
        "is_demo_scenario": False,
        "institution_name": "Fictional South Institute of Technology 02",
        "institution_identifier": "DEMO-AICTE-0002",
        "associated_case_id": "CC-2026-00002",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.APPROVAL_LETTER.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.PASSED.value,
        "expected_recommended_action": "Document satisfies all mandatory AICTE pre-scrutiny criteria and institution registry alignment.",
        "description": "Re-issued corrigendum EOA with corrected permanent institute ID DEMO-AICTE-0002.",
        "ocr_text": """ALL INDIA COUNCIL FOR TECHNICAL EDUCATION
Nelson Mandela Marg, Vasant Kunj, New Delhi-110070

APPROVAL PROCESS 2024-25
Corrigendum Extension of Approval (EOA)
F.No. South/1-9318281029/2024/EOA/CORR
Date: 15-Jun-2024

To,
The Principal,
Fictional South Institute of Technology 02

Sub: Corrigendum to Extension of Approval for Academic Year 2024-25
Permanent Institute Id: DEMO-AICTE-0002
Application Id: 1-9318281029
Name of the Institution: Fictional South Institute of Technology 02
Academic Year: 2024-25
Approved Intake: 300

Member Secretary, AICTE""",
    },
    {
        "fixture_id": "SYN-APP-07-POOR-OCR",
        "category": DocumentCategory.APPROVAL_LETTER,
        "scenario": "POOR OCR INPUT",
        "is_demo_scenario": False,
        "institution_name": "Fictional South Institute of Technology 02",
        "institution_identifier": "DEMO-AICTE-0002",
        "associated_case_id": "CC-2026-00002",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.APPROVAL_LETTER.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.NEEDS_HUMAN_REVIEW.value,
        "expected_recommended_action": "No outright rule violations detected, but text clarity or confidence warrants officer manual review before acceptance.",
        "description": "Fragmented scan of AICTE EOA with missing words and faint text.",
        "ocr_text": """ALL 1ND1A C0UNC1L F0R T3CHN1C@L 3DUCAT10N
N3ls0n M@nd3la M@rg N3w D3lh1
F.N0. S0uth/1-9318/2024/E0A
D@t3: 2024

N@me: Fictional South Institute of Technology 02
P3rm@n3nt Id: DEMO-AICTE-0002
Ac@d3mic Y3@r: 2024-25
Appr0v3d Int@k3: 300
M3mb3r S3cr3t@ry""",
    },

    # =========================================================================
    # CATEGORY 3: INSTITUTION REGISTRATION (SOCIETY / TRUST)
    # =========================================================================
    {
        "fixture_id": "SYN-REG-01-VALID",
        "category": DocumentCategory.INSTITUTION_REGISTRATION,
        "scenario": "VALID DOCUMENT",
        "is_demo_scenario": False,
        "institution_name": "Fictional East Institute of Technology 03",
        "institution_identifier": "DEMO-AICTE-0003",
        "associated_case_id": "CC-2026-00003",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.INSTITUTION_REGISTRATION.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.PASSED.value,
        "expected_recommended_action": "Document satisfies all mandatory AICTE pre-scrutiny criteria and institution registry alignment.",
        "description": "Legitimate, authenticated Certificate of Registration of Society under Societies Registration Act, 1860.",
        "ocr_text": """GOVERNMENT OF THE STATE
OFFICE OF THE REGISTRAR OF SOCIETIES & FIRMS
ADMINISTRATIVE SECRETARIAT, REGISTRATION WING

CERTIFICATE OF REGISTRATION OF SOCIETY
Registration Number: SOC/REG/2012/9847
Date of Registration: 18 March 2012

I hereby certify that Fictional East Educational and Charitable Society has this day been registered under the Societies Registration Act, 1860 (Act XXI of 1860).

Society Details:
Name of Society: Fictional East Educational and Charitable Society
Registered Office: 12-B Vidyapeeth Enclave, Institutional Area, Eastern Hub - 700016
Aims & Objects: Establishment, governance and maintenance of higher technical educational institutions including Fictional East Institute of Technology 03.

Given under my hand and seal at the District Registration Office.

Seal: [OFFICE OF REGISTRAR OF SOCIETIES]
Sd/-
Registrar of Societies
District Registration Office""",
    },
    {
        "fixture_id": "SYN-REG-02-MISSING",
        "category": DocumentCategory.INSTITUTION_REGISTRATION,
        "scenario": "MISSING INFORMATION",
        "is_demo_scenario": True,
        "demo_title": "Demo 4: Missing Registration Number in Society Registration",
        "institution_name": "Fictional East Institute of Technology 03",
        "institution_identifier": "DEMO-AICTE-0003",
        "associated_case_id": "CC-2026-00003",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.INSTITUTION_REGISTRATION.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.FLAGGED.value,
        "expected_recommended_action": "Scrutiny officer should review findings and dispatch formal deficiency notice to the institution.",
        "description": "Society registration certificate completely omitting the mandatory registration serial number and governing Act.",
        "ocr_text": """GOVERNMENT OF THE STATE
OFFICE OF THE REGISTRAR OF SOCIETIES

CERTIFICATE OF REGISTRATION
Date: 12 January 2015

This is to certify that Fictional East Educational and Charitable Society has been formed for educational purposes.
Registered Address: Institutional Area, Eastern Hub.

[REGISTRATION NUMBER OMITTED / BLANK FIELD]
[STATUTORY GOVERNING ACT NOT STATED]

Sd/-
Assistant Officer""",
    },
    {
        "fixture_id": "SYN-REG-03-EXPIRED",
        "category": DocumentCategory.INSTITUTION_REGISTRATION,
        "scenario": "INVALID OR EXPIRED INFORMATION",
        "is_demo_scenario": False,
        "institution_name": "Fictional East Institute of Technology 03",
        "institution_identifier": "DEMO-AICTE-0003",
        "associated_case_id": "CC-2026-00003",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.INSTITUTION_REGISTRATION.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.FLAGGED.value,
        "expected_recommended_action": "Scrutiny officer should review findings and dispatch formal deficiency notice to the institution.",
        "description": "Temporary 3-year society registration that lapsed in 2019 without renewal.",
        "ocr_text": """OFFICE OF THE REGISTRAR OF SOCIETIES

TEMPORARY PROVISIONAL REGISTRATION
Registration Number: SOC/TEMP/2016-11
Date of Registration: 10 May 2016

Name of Society: Fictional East Educational Society
Governing Act: Societies Registration Act, 1860

Validity Clause:
This registration is strictly provisional and valid up to 09 May 2019. Renewal must be filed annually.

Registrar of Societies""",
    },
    {
        "fixture_id": "SYN-REG-04-MISMATCH",
        "category": DocumentCategory.INSTITUTION_REGISTRATION,
        "scenario": "INSTITUTION MISMATCH",
        "is_demo_scenario": False,
        "institution_name": "Fictional North Institute of Technology 01",
        "institution_identifier": "DEMO-AICTE-0001",
        "associated_case_id": "CC-2026-00001",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.INSTITUTION_REGISTRATION.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.PASSED.value,
        "expected_recommended_action": "Document satisfies all mandatory AICTE pre-scrutiny criteria and institution registry alignment.",
        "description": "Trust deed registered under parent educational trust running North college.",
        "ocr_text": """GOVERNMENT OF THE STATE
OFFICE OF THE CHARITY COMMISSIONER

TRUST REGISTRATION CERTIFICATE
Registration Number: TR/DEL/2010/5541
Date: 14 August 2010

This is to certify that Fictional North Educational and Research Trust has been duly registered under the Indian Trusts Act, 1882.
Registered Office: North Tech Park, Sector 5, Delhi.

Registrar of Societies""",
    },
    {
        "fixture_id": "SYN-REG-05-INCONSISTENT",
        "category": DocumentCategory.INSTITUTION_REGISTRATION,
        "scenario": "INCONSISTENT INFORMATION",
        "is_demo_scenario": False,
        "institution_name": "Fictional East Institute of Technology 03",
        "institution_identifier": "DEMO-AICTE-0003",
        "associated_case_id": "CC-2026-00003",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.INSTITUTION_REGISTRATION.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.FLAGGED.value,
        "expected_recommended_action": "Scrutiny officer should review findings and dispatch formal deficiency notice to the institution.",
        "description": "Inconsistent registration dates (mentions registered on 2023 under an Act of 1860 with conflicting renewal years).",
        "ocr_text": """OFFICE OF THE REGISTRAR OF SOCIETIES
Registration Number: SOC/ERR/2023/10

Name of Society: Fictional East Educational Society
under the Societies Registration Act, 1860
Date of Registration: 31-02-2023 (Invalid date format)

Registrar of Societies""",
    },
    {
        "fixture_id": "SYN-REG-06-CORRECTED",
        "category": DocumentCategory.INSTITUTION_REGISTRATION,
        "scenario": "CORRECTED DOCUMENT",
        "is_demo_scenario": False,
        "institution_name": "Fictional East Institute of Technology 03",
        "institution_identifier": "DEMO-AICTE-0003",
        "associated_case_id": "CC-2026-00003",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.INSTITUTION_REGISTRATION.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.PASSED.value,
        "expected_recommended_action": "Document satisfies all mandatory AICTE pre-scrutiny criteria and institution registry alignment.",
        "description": "Authenticated duplicate registration certificate with official stamp and valid serial number.",
        "ocr_text": """OFFICE OF THE REGISTRAR OF SOCIETIES & FIRMS

CERTIFICATE OF REGISTRATION (AUTHENTICATED DUPLICATE)
Registration Number: SOC/REG/2012/9847-R
Date of Registration: 18 March 2012

Certified that Fictional East Educational and Charitable Society is registered under the Societies Registration Act, 1860.
Registered Office: 12-B Vidyapeeth Enclave, Institutional Area, Eastern Hub.

Issued under the hand and seal of the Registrar of Societies.

Sd/-
Registrar of Societies""",
    },
    {
        "fixture_id": "SYN-REG-07-POOR-OCR",
        "category": DocumentCategory.INSTITUTION_REGISTRATION,
        "scenario": "POOR OCR INPUT",
        "is_demo_scenario": False,
        "institution_name": "Fictional East Institute of Technology 03",
        "institution_identifier": "DEMO-AICTE-0003",
        "associated_case_id": "CC-2026-00003",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.INSTITUTION_REGISTRATION.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.NEEDS_HUMAN_REVIEW.value,
        "expected_recommended_action": "No outright rule violations detected, but text clarity or confidence warrants officer manual review before acceptance.",
        "description": "Old yellowed scanned parchment with heavy noise and faint stamp.",
        "ocr_text": """0FF1C3 0F R3G1STR@R 0F S0C13T13S
C3RT1F1C@T3 0F R3G1STR@T10N
R3g. N0: SOC/REG/2012/9847
D@t3: 18 M@rch 2012
S0c13ty: Fictional East Educational Society
und3r S0c13t13s R3g1str@t10n Act 1860
R3g1str@r 0f S0c13t13s""",
    },

    # =========================================================================
    # CATEGORY 4: FACULTY DETAILS STATEMENT
    # =========================================================================
    {
        "fixture_id": "SYN-FAC-01-VALID",
        "category": DocumentCategory.FACULTY_STATEMENT,
        "scenario": "VALID DOCUMENT",
        "is_demo_scenario": False,
        "institution_name": "Fictional West Institute of Technology 04",
        "institution_identifier": "DEMO-AICTE-0004",
        "associated_case_id": "CC-2026-00004",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.FACULTY_STATEMENT.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.PASSED.value,
        "expected_recommended_action": "Document satisfies all mandatory AICTE pre-scrutiny criteria and institution registry alignment.",
        "description": "Full faculty roster complying with AICTE 1:20 Student-Faculty Ratio and 1:2:6 cadre ratio.",
        "ocr_text": """FICTIONAL WEST INSTITUTE OF TECHNOLOGY 04
Approved by AICTE, New Delhi & Affiliated to State Technical University
Campus Boulevard, Tech Hub West - 400001

STATEMENT OF TEACHING FACULTY MEMBERS & CADRE RATIO
Academic Year: 2024-25
Date of Verification: 10 June 2024

SUMMARY OF TEACHING FACULTY:
Institution Name: Fictional West Institute of Technology 04
Total Student Enrollment: 1200

Cadre Breakdown:
- Professors Count: 8
- Associate Professors Count: 16
- Assistant Professors Count: 48
Total Faculty Count: 72

Calculations:
Cadre Ratio: 1 : 2 : 6
Student-Faculty Ratio (SFR): 1:16.6

We hereby certify that all 72 faculty members possess AICTE prescribed minimum educational qualifications (M.Tech / Ph.D.) and are paid as per 7th Central Pay Commission scales.

Sd/-
Principal
Fictional West Institute of Technology 04""",
    },
    {
        "fixture_id": "SYN-FAC-02-MISSING",
        "category": DocumentCategory.FACULTY_STATEMENT,
        "scenario": "MISSING INFORMATION",
        "is_demo_scenario": False,
        "institution_name": "Fictional West Institute of Technology 04",
        "institution_identifier": "DEMO-AICTE-0004",
        "associated_case_id": "CC-2026-00004",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.FACULTY_STATEMENT.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.FLAGGED.value,
        "expected_recommended_action": "Scrutiny officer should review findings and dispatch formal deficiency notice to the institution.",
        "description": "Faculty statement omitting student-faculty ratio and total faculty count.",
        "ocr_text": """FICTIONAL WEST INSTITUTE OF TECHNOLOGY 04
FACULTY ROSTER
Academic Year: 2024-25

List of departments and faculty names submitted.
[TOTAL FACULTY COUNT MISSING]
[STUDENT FACULTY RATIO NOT CALCULATED]

Sd/-
Principal""",
    },
    {
        "fixture_id": "SYN-FAC-03-EXPIRED",
        "category": DocumentCategory.FACULTY_STATEMENT,
        "scenario": "INVALID OR EXPIRED INFORMATION",
        "is_demo_scenario": False,
        "institution_name": "Fictional West Institute of Technology 04",
        "institution_identifier": "DEMO-AICTE-0004",
        "associated_case_id": "CC-2026-00004",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.FACULTY_STATEMENT.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.FLAGGED.value,
        "expected_recommended_action": "Scrutiny officer should review findings and dispatch formal deficiency notice to the institution.",
        "description": "Faculty statement submitted for past session 2020-21.",
        "ocr_text": """FICTIONAL WEST INSTITUTE OF TECHNOLOGY 04
TEACHING STAFF DETAILS
Academic Year: 2020-21

Total Faculty Count: 60
Professors Count: 6
Associate Professors Count: 12
Assistant Professors Count: 42
Student Faculty Ratio: 1:18

Principal""",
    },
    {
        "fixture_id": "SYN-FAC-04-MISMATCH",
        "category": DocumentCategory.FACULTY_STATEMENT,
        "scenario": "INSTITUTION MISMATCH",
        "is_demo_scenario": False,
        "institution_name": "Fictional North Institute of Technology 01",
        "institution_identifier": "DEMO-AICTE-0001",
        "associated_case_id": "CC-2026-00001",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.FACULTY_STATEMENT.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.FLAGGED.value,
        "expected_recommended_action": "Scrutiny officer should review findings and dispatch formal deficiency notice to the institution.",
        "description": "Faculty roster from Western institute uploaded for Northern institute.",
        "ocr_text": """FICTIONAL WEST INSTITUTE OF TECHNOLOGY 04
STATEMENT OF TEACHING FACULTY
Academic Year: 2024-25

Institution: Fictional West Institute of Technology 04
Total Faculty Count: 72
Student Faculty Ratio: 1:16.6

Principal""",
    },
    {
        "fixture_id": "SYN-FAC-05-INCONSISTENT",
        "category": DocumentCategory.FACULTY_STATEMENT,
        "scenario": "INCONSISTENT INFORMATION",
        "is_demo_scenario": True,
        "demo_title": "Demo 5: Arithmetical Discrepancy & Violating SFR in Faculty Statement",
        "institution_name": "Fictional West Institute of Technology 04",
        "institution_identifier": "DEMO-AICTE-0004",
        "associated_case_id": "CC-2026-00004",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.FACULTY_STATEMENT.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.FLAGGED.value,
        "expected_recommended_action": "Scrutiny officer should review findings and dispatch formal deficiency notice to the institution.",
        "description": "Blatant SFR violation (1:26.5 > 1:20 norm) and cadre arithmetic mismatch (3+8+25 = 36 != 60).",
        "ocr_text": """FICTIONAL WEST INSTITUTE OF TECHNOLOGY 04
CAMPUS FACULTY ROSTER
Academic Year: 2024-25
Dated: 05 June 2024

Name of the Institution: Fictional West Institute of Technology 04
Total Approved Student Enrollment: 960

Teaching Staff Distribution:
- Professors Count: 3
- Associate Professors Count: 8
- Assistant Professors Count: 25
Total Faculty Count: 60

Noticeable calculations:
Cadre Ratio: 1:2:8
Student Faculty Ratio: 1:26.5

We submit this faculty list for approval.

Sd/-
Principal
Fictional West Institute of Technology 04""",
    },
    {
        "fixture_id": "SYN-FAC-06-CORRECTED",
        "category": DocumentCategory.FACULTY_STATEMENT,
        "scenario": "CORRECTED DOCUMENT",
        "is_demo_scenario": False,
        "institution_name": "Fictional West Institute of Technology 04",
        "institution_identifier": "DEMO-AICTE-0004",
        "associated_case_id": "CC-2026-00004",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.FACULTY_STATEMENT.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.PASSED.value,
        "expected_recommended_action": "Document satisfies all mandatory AICTE pre-scrutiny criteria and institution registry alignment.",
        "description": "Corrected faculty statement after new recruitments, restoring SFR to 1:16.0 and reconciling numbers.",
        "ocr_text": """FICTIONAL WEST INSTITUTE OF TECHNOLOGY 04
REVISED AND CERTIFIED FACULTY STATEMENT
Academic Year: 2024-25
Date: 28 July 2024

Name of the Institution: Fictional West Institute of Technology 04
Total Approved Student Enrollment: 960

Revised Cadre Breakdown:
- Professors Count: 6
- Associate Professors Count: 14
- Assistant Professors Count: 40
Total Faculty Count: 60

Student Faculty Ratio: 1:16.0
Cadre Ratio: 1:2:6

All newly appointed faculty members hold recognized qualifications.

Sd/-
Principal
Fictional West Institute of Technology 04""",
    },
    {
        "fixture_id": "SYN-FAC-07-POOR-OCR",
        "category": DocumentCategory.FACULTY_STATEMENT,
        "scenario": "POOR OCR INPUT",
        "is_demo_scenario": False,
        "institution_name": "Fictional West Institute of Technology 04",
        "institution_identifier": "DEMO-AICTE-0004",
        "associated_case_id": "CC-2026-00004",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.FACULTY_STATEMENT.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.NEEDS_HUMAN_REVIEW.value,
        "expected_recommended_action": "No outright rule violations detected, but text clarity or confidence warrants officer manual review before acceptance.",
        "description": "Scanned table with skewed alignment and character glitches.",
        "ocr_text": """F1CT10N@L W3ST 1NST1TUT3 0F T3CHN0L0GY 04
FACULTY D3T@1LS ST@T3M3NT
Ac@d3m1c Y3@r: 2024-25
T0t@l F@culty: 72
Pr0f3ss0rs: 8 | Ass0c: 16 | Asst: 48
Stud3nt F@culty R@t10: 1:16.6
Pr1nc1p@l""",
    },

    # =========================================================================
    # CATEGORY 5: INFRASTRUCTURE REPORT
    # =========================================================================
    {
        "fixture_id": "SYN-INF-01-VALID",
        "category": DocumentCategory.INFRASTRUCTURE_REPORT,
        "scenario": "VALID DOCUMENT",
        "is_demo_scenario": False,
        "institution_name": "Fictional North Institute of Technology 05",
        "institution_identifier": "DEMO-AICTE-0005",
        "associated_case_id": "CC-2026-00005",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.INFRASTRUCTURE_REPORT.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.PASSED.value,
        "expected_recommended_action": "Document satisfies all mandatory AICTE pre-scrutiny criteria and institution registry alignment.",
        "description": "Architect-certified comprehensive infrastructure statement with 10.5 acres contiguous land and valid Fire Safety NOC.",
        "ocr_text": """ARCHITECTURAL & CIVIL ENGINEERING APPRAISAL REPORT
PHYSICAL INFRASTRUCTURE AND BUILT-UP AREA CERTIFICATE
Date of Inspection: 14 May 2024

Institution: Fictional North Institute of Technology 05
Campus Location: Sector 22, Green Valley Knowledge Park - 110045

LAND AND BUILT-UP AREA DETAILS:
1. Total Land Area: 10.5 Acres (Single Contiguous Plot)
2. Total Built-up Area: 22,500 sq.m
3. Instructional Area: 14,200 sq.m
4. Administrative Area: 3,500 sq.m
5. Amenities Area: 4,800 sq.m

FACILITIES BREAKDOWN:
- Number of Classrooms: 36 (each > 66 sq.m, well-ventilated)
- Number of Laboratories: 42 functional labs
- Computer Centers: 4 centers with 450 internet-connected terminals
- Library: 1,200 sq.m with digital reading section

SAFETY & REGULATORY CLEARANCES:
- Fire Safety Certificate: Valid Fire Safety NOC issued by State Fire Services Department (Ref: FS/NOC/2024/771, Valid Till 31-12-2026).
- Barrier-Free Access: Lifts, ramps, and dedicated toilets provided.

This is to certify that the campus infrastructure conforms strictly to AICTE Approval Process Handbook (APH) specifications.

Er. K. S. Sharma, B.Arch, FIIA
Registered Architect & Chartered Engineer
Registration No: CA/2004/31892""",
    },
    {
        "fixture_id": "SYN-INF-02-MISSING",
        "category": DocumentCategory.INFRASTRUCTURE_REPORT,
        "scenario": "MISSING INFORMATION",
        "is_demo_scenario": False,
        "institution_name": "Fictional North Institute of Technology 05",
        "institution_identifier": "DEMO-AICTE-0005",
        "associated_case_id": "CC-2026-00005",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.INFRASTRUCTURE_REPORT.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.FLAGGED.value,
        "expected_recommended_action": "Scrutiny officer should review findings and dispatch formal deficiency notice to the institution.",
        "description": "Infrastructure report missing land area, instructional area, and fire safety certificate.",
        "ocr_text": """INFRASTRUCTURE REPORT
Institution: Fictional North Institute of Technology 05
Total Built-up Area: 18,000 sq.m

Number of Classrooms: 20
Number of Laboratories: 15

[LAND AREA OMITTED]
[INSTRUCTIONAL AREA OMITTED]
[NO FIRE SAFETY NOC ATTACHED]

Chartered Engineer""",
    },
    {
        "fixture_id": "SYN-INF-03-EXPIRED",
        "category": DocumentCategory.INFRASTRUCTURE_REPORT,
        "scenario": "INVALID OR EXPIRED INFORMATION",
        "is_demo_scenario": False,
        "institution_name": "Fictional North Institute of Technology 05",
        "institution_identifier": "DEMO-AICTE-0005",
        "associated_case_id": "CC-2026-00005",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.INFRASTRUCTURE_REPORT.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.FLAGGED.value,
        "expected_recommended_action": "Scrutiny officer should review findings and dispatch formal deficiency notice to the institution.",
        "description": "Infrastructure report showing expired Fire Safety NOC.",
        "ocr_text": """PHYSICAL INFRASTRUCTURE REPORT
Institution: Fictional North Institute of Technology 05
Total Land Area: 7.5 Acres
Total Built-up Area: 18,000 sq.m
Instructional Area: 11,000 sq.m

Fire Safety Certificate: Expired on 10-01-2023 (Renewal pending with Fire Department)
Number of Classrooms: 24
Laboratories: 28

Chartered Engineer""",
    },
    {
        "fixture_id": "SYN-INF-04-MISMATCH",
        "category": DocumentCategory.INFRASTRUCTURE_REPORT,
        "scenario": "INSTITUTION MISMATCH",
        "is_demo_scenario": False,
        "institution_name": "Fictional South Institute of Technology 02",
        "institution_identifier": "DEMO-AICTE-0002",
        "associated_case_id": "CC-2026-00002",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.INFRASTRUCTURE_REPORT.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.FLAGGED.value,
        "expected_recommended_action": "Scrutiny officer should review findings and dispatch formal deficiency notice to the institution.",
        "description": "Infrastructure report belonging to Northern institute uploaded under Southern case.",
        "ocr_text": """CAMPUS INFRASTRUCTURE APPRAISAL
Institution: Fictional North Institute of Technology 05
Land Area: 10.5 Acres
Total Built-up Area: 22,500 sq.m
Instructional Area: 14,200 sq.m
Fire Safety Certificate: Valid Fire Safety NOC Valid

Chartered Engineer""",
    },
    {
        "fixture_id": "SYN-INF-05-INCONSISTENT",
        "category": DocumentCategory.INFRASTRUCTURE_REPORT,
        "scenario": "INCONSISTENT INFORMATION",
        "is_demo_scenario": True,
        "demo_title": "Demo 6: Inconsistent Area Breakdown & Expired Fire Safety in Infrastructure Report",
        "institution_name": "Fictional North Institute of Technology 05",
        "institution_identifier": "DEMO-AICTE-0005",
        "associated_case_id": "CC-2026-00005",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.INFRASTRUCTURE_REPORT.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.FLAGGED.value,
        "expected_recommended_action": "Scrutiny officer should review findings and dispatch formal deficiency notice to the institution.",
        "description": "Impossible geometry where instructional area (16,000 sq.m) exceeds total built-up area (12,000 sq.m) with expired Fire NOC.",
        "ocr_text": """BUILDING SAFETY & AREA ASSESSMENT
Institution: Fictional North Institute of Technology 05
Date: 20 May 2024

AREA SPECIFICATIONS:
Total Land Area: 5.0 Acres
Total Built-up Area: 12,000 sq.m
Instructional Area: 16,000 sq.m
Administrative Area: 3,000 sq.m

Number of Classrooms: 25
Number of Laboratories: 20
Fire Safety Certificate: Expired Fire NOC (Application for re-inspection filed)

This report is submitted for annual inspection.

Chartered Engineer""",
    },
    {
        "fixture_id": "SYN-INF-06-CORRECTED",
        "category": DocumentCategory.INFRASTRUCTURE_REPORT,
        "scenario": "CORRECTED DOCUMENT",
        "is_demo_scenario": False,
        "institution_name": "Fictional North Institute of Technology 05",
        "institution_identifier": "DEMO-AICTE-0005",
        "associated_case_id": "CC-2026-00005",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.INFRASTRUCTURE_REPORT.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.PASSED.value,
        "expected_recommended_action": "Document satisfies all mandatory AICTE pre-scrutiny criteria and institution registry alignment.",
        "description": "Rectified area survey and renewed Fire Safety clearance.",
        "ocr_text": """ARCHITECTURAL RE-SURVEY & CERTIFICATE
Institution: Fictional North Institute of Technology 05
Date: 15 July 2024

RECONCILED MEASUREMENTS:
Total Land Area: 5.0 Acres
Total Built-up Area: 20,000 sq.m
Instructional Area: 12,500 sq.m
Administrative Area: 3,500 sq.m
Amenities Area: 4,000 sq.m

Number of Classrooms: 28
Number of Laboratories: 24
Fire Safety Certificate: Valid Fire Safety NOC Issued (Valid till 2026)

Chartered Engineer""",
    },
    {
        "fixture_id": "SYN-INF-07-POOR-OCR",
        "category": DocumentCategory.INFRASTRUCTURE_REPORT,
        "scenario": "POOR OCR INPUT",
        "is_demo_scenario": False,
        "institution_name": "Fictional North Institute of Technology 05",
        "institution_identifier": "DEMO-AICTE-0005",
        "associated_case_id": "CC-2026-00005",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.INFRASTRUCTURE_REPORT.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.NEEDS_HUMAN_REVIEW.value,
        "expected_recommended_action": "No outright rule violations detected, but text clarity or confidence warrants officer manual review before acceptance.",
        "description": "Faded blueprint scan with low contrast text.",
        "ocr_text": """1NFR@STRUCTUR3 R3P0RT
1nst1tut10n: Fictional North Institute of Technology 05
L@nd Ar3a: 10.5 Acres
Bu1lt-up Ar3a: 22,500 sq.m
Instruct10n@l: 14,200 sq.m
F1r3 S@f3ty: V@l1d Fire Safety NOC Valid
Ch@rt3r3d Eng1n33r""",
    },

    # =========================================================================
    # UNSUPPORTED / CONTROL DOCUMENTS & CORRUPT TEST CASES
    # =========================================================================
    {
        "fixture_id": "SYN-UNS-01-UTILITY-BILL",
        "category": DocumentCategory.UNSUPPORTED,
        "scenario": "UNSUPPORTED DOCUMENT",
        "is_demo_scenario": True,
        "demo_title": "Demo 7: Unsupported Utility Bill Upload",
        "institution_name": "Fictional North Institute of Technology 01",
        "institution_identifier": "DEMO-AICTE-0001",
        "associated_case_id": "CC-2026-00001",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.UNSUPPORTED.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.UNSUPPORTED.value,
        "expected_recommended_action": "Unsupported document type uploaded. Reject submission and request valid AICTE regulatory documentation.",
        "description": "Monthly commercial electricity bill uploaded erroneously instead of an institutional compliance document.",
        "ocr_text": """STATE ELECTRICITY DISTRIBUTION CORPORATION LIMITED
COMMERCIAL POWER TARIFF BILL & CONSUMER INVOICE
Consumer Number: LT-COM-8839210
Billing Cycle: MAY 2024
Due Date: 15-06-2024

Consumer Name: Fictional North Institute of Technology
Meter Number: MTR-99201-B
Sanctioned Load: 150 kW
Current Reading: 45,920 kWh
Previous Reading: 38,100 kWh
Units Consumed: 7,820 kWh

Current Energy Charges: Rs. 62,560.00
Fixed Demand Charges: Rs. 15,000.00
Electricity Duty (9%): Rs. 6,980.40
Total Amount Payable: Rs. 84,540.40

Payment Counter: Online Net Banking / UPI accepted. Disconnection notice applies after grace period.""",
    },
    {
        "fixture_id": "SYN-UNS-02-MENU",
        "category": DocumentCategory.UNSUPPORTED,
        "scenario": "UNSUPPORTED DOCUMENT",
        "is_demo_scenario": False,
        "institution_name": "Fictional North Institute of Technology 01",
        "institution_identifier": "DEMO-AICTE-0001",
        "associated_case_id": "CC-2026-00001",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.UNSUPPORTED.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.UNSUPPORTED.value,
        "expected_recommended_action": "Unsupported document type uploaded. Reject submission and request valid AICTE regulatory documentation.",
        "description": "Campus cafeteria food menu card.",
        "ocr_text": """ROYAL CAMPUS CAFE & CANTEEN
DAILY SPECIAL MENU & CATERING TARIFF
Appetizers:
- Veg Spring Rolls: Rs. 60
- Paneer Tikka: Rs. 110
- Crispy Corn: Rs. 70

Main Course:
- Dal Makhani Combo: Rs. 90
- Butter Naan: Rs. 25
- Veg Biryani: Rs. 120

Beverages:
- Masala Chai: Rs. 15
- Cold Coffee: Rs. 40
Order Timings: 8:00 AM to 9:30 PM""",
    },
    {
        "fixture_id": "SYN-UNS-03-RESUME",
        "category": DocumentCategory.UNSUPPORTED,
        "scenario": "UNSUPPORTED DOCUMENT",
        "is_demo_scenario": False,
        "institution_name": "Fictional North Institute of Technology 01",
        "institution_identifier": "DEMO-AICTE-0001",
        "associated_case_id": "CC-2026-00001",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.UNSUPPORTED.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.UNSUPPORTED.value,
        "expected_recommended_action": "Unsupported document type uploaded. Reject submission and request valid AICTE regulatory documentation.",
        "description": "Personal Curriculum Vitae / Resume of an applicant.",
        "ocr_text": """CURRICULUM VITAE
Rohan Gupta
Email: rohan.gupta.dev@example.com | Phone: +91 9876543210
LinkedIn: linkedin.com/in/rohan-gupta-dev

CAREER OBJECTIVE:
Seeking a challenging position as Senior Assistant Professor in Computer Science and Engineering.

EDUCATION:
- M.Tech in Computer Science, IIT Delhi (2018-2020) - CGPA 8.9
- B.Tech in Information Technology, State Tech University (2014-2018) - 84%

TECHNICAL SKILLS:
Python, PyTorch, C++, Machine Learning, Distributed Systems, SQL.

PUBLICATIONS:
3 papers published in IEEE Transactions on Cloud Computing.""",
    },
    {
        "fixture_id": "SYN-COR-01-TRUNCATED-SCAN",
        "category": DocumentCategory.AFFILIATION_CERTIFICATE,
        "scenario": "POOR OCR INPUT",
        "is_demo_scenario": True,
        "demo_title": "Demo 8: Truncated & Heavily Degraded OCR Scan",
        "institution_name": "Fictional North Institute of Technology 01",
        "institution_identifier": "DEMO-AICTE-0001",
        "associated_case_id": "CC-2026-00001",
        "academic_year": "2024-25",
        "expected_classification": DocumentCategory.AFFILIATION_CERTIFICATE.value,
        "expected_pre_scrutiny_status": PreScrutinyStatus.NEEDS_HUMAN_REVIEW.value,
        "expected_recommended_action": "No outright rule violations detected, but text clarity or confidence warrants officer manual review before acceptance.",
        "description": "Severely truncated 2-line snippet failing minimum length criteria and requiring manual scrutiny verification.",
        "ocr_text": """ST@TE TECH UNIV... AFFIL...
Fictional North Inst... 2024...""",
    },
]


def get_all_fixtures() -> list[dict[str, Any]]:
    """Returns the complete list of synthetic fixtures."""
    return SYNTHETIC_FIXTURES


def get_fixture_by_id(fixture_id: str) -> dict[str, Any] | None:
    """Finds a synthetic fixture by its ID."""
    for f in SYNTHETIC_FIXTURES:
        if f["fixture_id"] == fixture_id:
            return f
    return None


def get_demo_scenarios() -> list[dict[str, Any]]:
    """Returns the 8 mandatory end-to-end demonstration scenarios."""
    return [f for f in SYNTHETIC_FIXTURES if f.get("is_demo_scenario")]
