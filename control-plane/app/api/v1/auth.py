from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select

from app.api.deps import get_session
from app.core.rate_limit import limiter
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])

# A fixed dummy hash to verify against when the email doesn't match any
# user, so a login attempt for a nonexistent account takes roughly the same
# time as one for a real account with a wrong password — otherwise the
# (fast) "no such user" path vs. the (bcrypt-slow) "wrong password" path is
# a timing side-channel an attacker can use to enumerate valid emails.
_DUMMY_HASH = hash_password("not-a-real-password-just-for-timing")


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, payload: LoginRequest, db=Depends(get_session)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    password_ok = verify_password(payload.password, user.hashed_password if user else _DUMMY_HASH)
    if user is None or not password_ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    token = create_access_token(user_id=user.id, org_id=user.org_id, role=user.role)
    return TokenResponse(access_token=token)
