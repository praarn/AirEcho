"""Request dependencies.

`current_user` decodes the access token. `scoped(...)` is the single choke point
for per-user data isolation: every route that touches personal data fetches it
through `scoped`, which adds `WHERE user_id = :current_user` at the query layer.
Route handlers never trust a `user_id` taken from a path/query param.
"""

from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database import get_db
from app.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=True)

DbDep = Annotated[Session, Depends(get_db)]


def current_user(token: Annotated[str, Depends(oauth2_scheme)], db: DbDep) -> User:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        user_id = decode_access_token(token)
    except jwt.PyJWTError:
        raise cred_exc from None
    user = db.get(User, user_id)
    if user is None:
        raise cred_exc
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def scoped(db: Session, model, user_id: int):
    """A SELECT already constrained to the caller. Callers add `.where(...)` for
    the specific row(s) but can never widen past their own user_id."""
    return select(model).where(model.user_id == user_id)


def get_owned_or_404(db: Session, model, user_id: int, obj_id: int):
    obj = db.execute(scoped(db, model, user_id).where(model.id == obj_id)).scalar_one_or_none()
    if obj is None:
        # 404 (not 403) so we don't leak whether the id exists for another user
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return obj
