"""Repeatable synthetic demonstration seed data. Never use as official records."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.database import SessionLocal
from app.enums import ActionType, CaseStatus, Priority, Role
from app.models import Bureau, Case, CaseEvent, Institution, User
from app.security import hash_password
from app.services import normalize_name

NOTICE = "Synthetic Demonstration Data — Not Official AICTE Records"

BUREAUS = [
    ("RB", "Regulation Bureau", None),
    ("PGRC", "Public Grievance Redressal Cell", None),
    ("APB", "Approval Bureau", None),
    ("FDP", "Faculty Development Cell", None),
    ("RO-SOUTH", "Southern Regional Office", "South"),
    ("RO-NORTH", "Northern Regional Office", "North"),
]

USERS = [
    ("admin@demo.example.com", "Demo Admin", Role.ADMIN, "RB", "ALL"),
    ("rb.officer@demo.example.com", "Riya Banerjee", Role.RB_OFFICER, "RB", None),
    ("pgrc.officer@demo.example.com", "Prakash Gupta", Role.PGRC_OFFICER, "PGRC", None),
    ("approval.officer@demo.example.com", "Asha Menon", Role.OTHER_BUREAU_OFFICER, "APB", None),
    ("fdp.officer@demo.example.com", "Farhan Khan", Role.OTHER_BUREAU_OFFICER, "FDP", None),
    ("south.ro@demo.example.com", "Sonal Rao", Role.REGIONAL_OFFICER, "RO-SOUTH", "South"),
    ("north.ro@demo.example.com", "Nikhil Sinha", Role.REGIONAL_OFFICER, "RO-NORTH", "North"),
    ("management@demo.example.com", "Meera Iyer", Role.SENIOR_MANAGEMENT, "RB", "ALL"),
    ("authority@demo.example.com", "Arun Das", Role.COMPETENT_AUTHORITY, "RB", "ALL"),
]


def seed() -> None:
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.email == "admin@demo.example.com")):
            print(f"{NOTICE}: already seeded; no records added.")
            return
        bureau_by_code: dict[str, Bureau] = {}
        for code, name, region in BUREAUS:
            bureau = Bureau(code=code, name=name, region=region)
            db.add(bureau)
            bureau_by_code[code] = bureau
        db.flush()
        user_by_email: dict[str, User] = {}
        for email, name, role, bureau_code, region_scope in USERS:
            user = User(email=email, full_name=name, password_hash=hash_password("DemoPass!2026"), role=role,
                        bureau_id=bureau_by_code[bureau_code].id, region_scope=region_scope)
            db.add(user)
            user_by_email[email] = user
        db.flush()
        states = [("North", "Uttar Pradesh"), ("South", "Tamil Nadu"), ("East", "West Bengal"), ("West", "Maharashtra")]
        institutions: list[Institution] = []
        for index in range(1, 21):
            region, state = states[(index - 1) % len(states)]
            name = f"Fictional {region} Institute of Technology {index:02d}"
            institution = Institution(permanent_id=f"DEMO-AICTE-{index:04d}", permanent_id_verified=index % 3 == 0,
                                      name=name, normalized_name=normalize_name(name), institution_type="Engineering College",
                                      address=f"{index} Demonstration Road", city=f"Demo City {index}", district=f"District {index}",
                                      state=state, region=region, status="Active")
            db.add(institution)
            institutions.append(institution)
        # Similar names are separate records; no automatic merge is performed.
        institutions[18].name = "Fictional South Institute of Technology Annex"
        institutions[18].normalized_name = normalize_name(institutions[18].name)
        institutions[19].name = "Fictional South Institute of Technologies"
        institutions[19].normalized_name = normalize_name(institutions[19].name)
        db.flush()
        officers = [user_by_email[email] for email in ("rb.officer@demo.example.com", "pgrc.officer@demo.example.com", "approval.officer@demo.example.com", "fdp.officer@demo.example.com")]
        status_cycle = [CaseStatus.RECEIVED, CaseStatus.UNDER_REVIEW, CaseStatus.UNDER_PROCESS, CaseStatus.PENDING_INSTITUTION_RESPONSE, CaseStatus.TRANSFERRED, CaseStatus.ESCALATED, CaseStatus.DISPOSED, CaseStatus.CLOSED]
        priorities = list(Priority)
        today = datetime.now(UTC)
        for index in range(1, 41):
            institution = institutions[(index - 1) % len(institutions)]
            bureau = bureau_by_code[["RB", "PGRC", "APB", "FDP"][index % 4]]
            status_value = status_cycle[(index - 1) % len(status_cycle)]
            officer = officers[index % len(officers)]
            subject = f"Synthetic demonstration matter {index}"
            if index == 1:
                institution, bureau, officer, subject = institutions[0], bureau_by_code["RB"], user_by_email["rb.officer@demo.example.com"], "Alleged approval-condition non-compliance"
            elif index == 2:
                institution, bureau, officer, subject = institutions[0], bureau_by_code["PGRC"], user_by_email["pgrc.officer@demo.example.com"], "Concern about compliance with approval conditions"
            elif index == 3:
                institution, bureau, officer, subject = institutions[0], bureau_by_code["PGRC"], user_by_email["pgrc.officer@demo.example.com"], "Unrelated hostel sanitation concern"
            created = today - timedelta(days=index * 2)
            case = Case(case_id=f"CC-{today.year}-{index:05d}", external_reference=f"SYN-{index:04d}", institution_id=institution.id,
                        receipt_at=created, receipt_date=created.date(), source_channel=["Portal", "Email", "Regional Office", "Helpline"][index % 4],
                        category=["Approval", "Grievance", "Infrastructure", "Faculty"][index % 4], subcategory="Synthetic category",
                        subject=subject, description=f"{NOTICE}. Detailed fictional complaint narrative {index}.", priority=priorities[index % 4],
                        originating_bureau_id=bureau.id, current_bureau_id=bureau.id, assigned_officer_id=officer.id, status=status_value,
                        last_action="Synthetic seeded workflow state", last_action_at=created + timedelta(days=1), next_action="Synthetic follow-up",
                        expected_disposal_date=today + timedelta(days=(index % 11) - 5), closure_date=(today - timedelta(days=index)) if status_value == CaseStatus.CLOSED else None)
            db.add(case)
            db.flush()
            db.add(CaseEvent(case_id=case.id, action_type=ActionType.CREATED, actor_id=user_by_email["admin@demo.example.com"].id, bureau_id=bureau.id,
                             new_values={"status": CaseStatus.RECEIVED.value}, remarks="Synthetic case created"))
            if status_value != CaseStatus.RECEIVED:
                db.add(CaseEvent(case_id=case.id, action_type=ActionType.STATUS_CHANGED, actor_id=officer.id, bureau_id=bureau.id,
                                 previous_values={"status": CaseStatus.RECEIVED.value}, new_values={"status": status_value.value}, remarks="Synthetic workflow update"))
        db.commit()
    print(NOTICE)
    print("Seed completed. Development login: admin@demo.example.com / DemoPass!2026")


if __name__ == "__main__":
    seed()
