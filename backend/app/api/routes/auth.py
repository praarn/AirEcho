from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep
from app.core.security import (
    create_access_token,
    hash_password,
    issue_refresh_token,
    revoke_all_for_user,
    rotate_refresh_token,
    verify_password,
)
from app.models import AuditLog, User
from app.schemas import LoginIn, RefreshIn, RegisterIn, TokenPair, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: RegisterIn, db: DbDep):
    if db.execute(select(User).where(User.email == body.email)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="email already registered")
    user = User(email=body.email, hashed_password=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    db.add(
        AuditLog(actor_id=user.id, action="register", target_table="users", target_id=str(user.id))
    )
    db.commit()
    return user


@router.post("/login", response_model=TokenPair)
def login(body: LoginIn, db: DbDep, request: Request):
    user = db.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    refresh = issue_refresh_token(db, user.id, request.headers.get("user-agent"))
    db.commit()
    return TokenPair(access_token=create_access_token(user.id), refresh_token=refresh)


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshIn, db: DbDep, request: Request):
    try:
        user_id, new_refresh = rotate_refresh_token(
            db, body.refresh_token, request.headers.get("user-agent")
        )
    except ValueError as exc:
        db.commit()  # persist chain-revocation on reuse detection
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from None
    db.commit()
    return TokenPair(access_token=create_access_token(user_id), refresh_token=new_refresh)


@router.post("/logout", status_code=204)
def logout(user: CurrentUser, db: DbDep):
    revoke_all_for_user(db, user.id)
    db.commit()


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user
