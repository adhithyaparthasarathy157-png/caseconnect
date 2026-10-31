import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import UTC, datetime
from app.database import SessionLocal
from app.models import Case, CaseSlaRecord
from sqlalchemy import select

now = datetime.now(UTC)
print(f"Current UTC timestamp: {now.isoformat()}")

with SessionLocal() as db:
    active_cases = db.scalars(
        select(Case).join(CaseSlaRecord)
        .where(CaseSlaRecord.status != 'COMPLETED')
        .order_by(CaseSlaRecord.status, Case.id)
    ).all()
    
    print(f"Total active cases: {len(active_cases)}")
    print(f"{'Case ID':<15} {'Status':<10} {'Receipt Date':<12} {'Deadline':<25} {'Past/Future':<12} {'Elapsed(h)':<10} {'Consumed%':<10}")
    print("-" * 98)
    
    past_count = 0
    future_count = 0
    for c in active_cases:
        r = c.sla_record
        dl = r.current_deadline
        dl_utc = dl.replace(tzinfo=UTC) if dl.tzinfo is None else dl
        is_past = "PAST" if dl_utc < now else "FUTURE"
        if is_past == "PAST":
            past_count += 1
        else:
            future_count += 1
        print(f"{c.case_id:<15} {r.status:<10} {str(c.receipt_date):<12} {str(dl):<25} {is_past:<12} {r.elapsed_duration_hours:<10} {r.consumed_percentage:<10}")

    print("-" * 98)
    print(f"Total PAST deadlines: {past_count}")
    print(f"Total FUTURE deadlines: {future_count}")
