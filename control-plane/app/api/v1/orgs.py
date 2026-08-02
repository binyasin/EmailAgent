import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import get_session
from app.core.security import CurrentUser, Role, hash_password, require_org_admin, require_org_scope
from app.models.org import Org
from app.models.user import User
from app.schemas.org import ChangeRoleRequest, InviteMemberRequest, InviteMemberResponse, OrgMemberOut
from app.services.audit import record_audit_event
from app.services.billing import enforce_plan_limit

router = APIRouter(prefix="/orgs", tags=["orgs"])

_ASSIGNABLE_ROLES = {Role.MEMBER.value, Role.ORG_ADMIN.value}


@router.get("/members", response_model=list[OrgMemberOut])
def list_members(db=Depends(get_session), user: CurrentUser = Depends(require_org_scope)):
    return db.scalars(select(User).where(User.org_id == user.org_id)).all()


@router.post("/invite", response_model=InviteMemberResponse, status_code=status.HTTP_201_CREATED)
def invite_member(
    payload: InviteMemberRequest,
    db=Depends(get_session),
    user: CurrentUser = Depends(require_org_admin),
):
    if payload.role not in _ASSIGNABLE_ROLES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Cannot assign role '{payload.role}'")

    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with this email already exists")

    org = db.get(Org, user.org_id)
    current_seats = db.scalar(
        select(func.count()).select_from(User).where(User.org_id == user.org_id)
    )
    enforce_plan_limit(plan_tier=org.plan_tier, resource="seats", current_count=current_seats)

    temp_password = secrets.token_urlsafe(16)
    new_user = User(
        org_id=user.org_id,
        email=payload.email,
        hashed_password=hash_password(temp_password),
        role=payload.role,
    )
    db.add(new_user)
    db.flush()

    record_audit_event(
        db,
        org_id=user.org_id,
        actor_type="user",
        actor_id=user.user_id,
        action="member.invited",
        resource_type="user",
        resource_id=new_user.id,
        metadata={"email": payload.email, "role": payload.role},
    )
    return InviteMemberResponse(user=new_user, temporary_password=temp_password)


@router.patch("/members/{member_id}/role", response_model=OrgMemberOut)
def change_member_role(
    member_id: str,
    payload: ChangeRoleRequest,
    db=Depends(get_session),
    user: CurrentUser = Depends(require_org_admin),
):
    if payload.role not in _ASSIGNABLE_ROLES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Cannot assign role '{payload.role}'")

    member = db.scalar(
        select(User).where(User.id == member_id, User.org_id == user.org_id)
    )
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")

    if member.role == Role.ORG_ADMIN.value and payload.role != Role.ORG_ADMIN.value:
        _ensure_not_last_org_admin(db, user.org_id, excluding_user_id=member.id)

    member.role = payload.role
    record_audit_event(
        db,
        org_id=user.org_id,
        actor_type="user",
        actor_id=user.user_id,
        action="member.role_changed",
        resource_type="user",
        resource_id=member.id,
        metadata={"new_role": payload.role},
    )
    return member


@router.delete("/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    member_id: str, db=Depends(get_session), user: CurrentUser = Depends(require_org_admin)
):
    member = db.scalar(
        select(User).where(User.id == member_id, User.org_id == user.org_id)
    )
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")

    if member.role == Role.ORG_ADMIN.value:
        _ensure_not_last_org_admin(db, user.org_id, excluding_user_id=member.id)

    db.delete(member)
    record_audit_event(
        db,
        org_id=user.org_id,
        actor_type="user",
        actor_id=user.user_id,
        action="member.removed",
        resource_type="user",
        resource_id=member_id,
        metadata={"email": member.email},
    )


def _ensure_not_last_org_admin(db, org_id: str, *, excluding_user_id: str) -> None:
    remaining_admins = db.scalar(
        select(func.count())
        .select_from(User)
        .where(
            User.org_id == org_id,
            User.role == Role.ORG_ADMIN.value,
            User.id != excluding_user_id,
        )
    )
    if remaining_admins == 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Cannot remove the last org_admin — promote another member first"
        )
