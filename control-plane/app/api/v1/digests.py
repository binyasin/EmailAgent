from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import get_session
from app.core.security import CurrentUser, require_org_scope
from app.models.digest_run import DigestRun
from app.schemas.digest import DigestRunOut

router = APIRouter(prefix="/digests", tags=["digests"])


@router.get("", response_model=list[DigestRunOut])
def list_digests(db=Depends(get_session), user: CurrentUser = Depends(require_org_scope)):
    return db.scalars(
        select(DigestRun)
        .where(DigestRun.org_id == user.org_id)
        .order_by(DigestRun.created_at.desc())
        .limit(50)
    ).all()
