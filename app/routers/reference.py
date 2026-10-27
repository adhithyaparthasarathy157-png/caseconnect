"""Authenticated lookup endpoints for workflow forms."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, is_broad_viewer
from app.models import Bureau, User
from app.schemas import BureauPublic, UserPublic

router = APIRouter(prefix="/api/reference", tags=["workflow reference data"])


@router.get("/bureaus", response_model=list[BureauPublic])
def list_bureaus(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[Bureau]:
    return list(db.scalars(select(Bureau).order_by(Bureau.code)).all())


@router.get("/officers", response_model=list[UserPublic])
def list_eligible_officers(bureau_id: int = Query(gt=0), db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[User]:
    if not (is_broad_viewer(user) or user.bureau_id == bureau_id):
        raise HTTPException(status_code=403, detail="Officer directory is outside your access scope")
    return list(db.scalars(select(User).where(User.bureau_id == bureau_id, User.is_active.is_(True)).order_by(User.full_name)).all())
