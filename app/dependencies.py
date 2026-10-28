from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.enums import Role
from app.models import Case, User
from app.security import decode_access_token

bearer = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)) -> User:
    user = db.get(User, decode_access_token(credentials.credentials))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive or unknown user")
    return user


def require_roles(*roles: Role) -> Callable:
    def check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role permission")
        return user
    return check


def is_broad_viewer(user: User) -> bool:
    return user.role in {Role.ADMIN, Role.SENIOR_MANAGEMENT, Role.COMPETENT_AUTHORITY}


def _regions(user: User) -> set[str]:
    return {item.strip().lower() for item in (user.region_scope or "").split(",") if item.strip()}


def can_view_case(user: User, case: Case) -> bool:
    if is_broad_viewer(user):
        return True
    if user.role == Role.REGIONAL_OFFICER:
        regions = _regions(user)
        return "all" in regions or case.institution.region.lower() in regions
    if user.role == Role.INSTITUTION_REPRESENTATIVE:
        return user.institution_id is not None and case.institution_id == user.institution_id
    return user.bureau_id in {case.current_bureau_id, case.originating_bureau_id}


def can_modify_case(user: User, case: Case) -> bool:
    if user.role in {Role.ADMIN, Role.COMPETENT_AUTHORITY}:
        return True
    if user.role == Role.SENIOR_MANAGEMENT:
        return False
    if user.role == Role.INSTITUTION_REPRESENTATIVE:
        return False
    if user.role == Role.REGIONAL_OFFICER:
        regions = _regions(user)
        return "all" in regions or case.institution.region.lower() in regions
    return user.bureau_id == case.current_bureau_id
