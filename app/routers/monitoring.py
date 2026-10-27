from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.enums import Role
from app.models import User
from app.monitoring import run_monitor

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.post("/run")
def run(warning_days: int = Query(7, ge=1, le=60), db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, int]:
    if user.role not in {Role.ADMIN, Role.COMPETENT_AUTHORITY}:
        raise HTTPException(status_code=403, detail="Only administrators may run the prototype monitor")
    return run_monitor(db, warning_days)
