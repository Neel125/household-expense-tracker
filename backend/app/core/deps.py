"""FastAPI dependencies: the current session and the authenticated user.

Controllers depend on `CurrentUser` to get an authenticated, household-
scoped identity. Everything hangs off the Bearer token issued at login.
"""
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlmodel import Session

from app.core.database import get_session
from app.core.security import decode_access_token
from app.models import User
from app.repositories.repositories import UserRepository

SessionDep = Annotated[Session, Depends(get_session)]


def get_current_user(
    session: SessionDep,
    authorization: str | None = Header(default=None),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Not authenticated")
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(401, "Invalid or expired session")
    user = UserRepository(session).get(int(payload["sub"]))
    if not user:
        raise HTTPException(401, "Account no longer exists")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_owner(user: CurrentUser) -> User:
    if user.role != "owner":
        raise HTTPException(403, "Only the household owner can do that")
    return user


OwnerUser = Annotated[User, Depends(require_owner)]
