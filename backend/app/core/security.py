"""JWT mint/verify, password hashing, and refresh-token rotation.

Refresh tokens are *opaque* random strings; only their SHA-256 hash is stored.
Every use rotates: the presented token is revoked and a fresh one issued, with
`rotated_to` recording the successor for a tamper trail. Re-use of an
already-rotated token revokes the whole chain (classic refresh-token reuse
detection).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import RefreshToken

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(raw: str) -> str:
    return _pwd.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    return _pwd.verify(raw, hashed)


def _now() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------------- #
# Access tokens (short-lived JWT)
# --------------------------------------------------------------------------- #
def create_access_token(user_id: int) -> str:
    now = _now()
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_ttl_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> int:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("wrong token type")
    return int(payload["sub"])


# --------------------------------------------------------------------------- #
# Refresh tokens (opaque, hashed at rest, rotated on use)
# --------------------------------------------------------------------------- #
def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def issue_refresh_token(db: Session, user_id: int, user_agent: str | None = None) -> str:
    raw = secrets.token_urlsafe(48)
    row = RefreshToken(
        user_id=user_id,
        token_hash=_sha256(raw),
        expires_at=_now() + timedelta(days=settings.refresh_token_ttl_days),
        user_agent=(user_agent or "")[:400] or None,
    )
    db.add(row)
    db.flush()
    return raw


def rotate_refresh_token(
    db: Session, presented: str, user_agent: str | None = None
) -> tuple[int, str]:
    """Returns (user_id, new_raw_refresh_token). Raises ValueError on any problem."""
    row = db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == _sha256(presented))
    ).scalar_one_or_none()

    if row is None:
        raise ValueError("unknown refresh token")

    if row.revoked:
        # reuse of a rotated token → treat the whole user's chain as compromised
        db.query(RefreshToken).filter(RefreshToken.user_id == row.user_id).update({"revoked": True})
        db.flush()
        raise ValueError("refresh token reuse detected — all sessions revoked")

    if row.expires_at.replace(tzinfo=UTC) < _now():
        raise ValueError("refresh token expired")

    new_raw = issue_refresh_token(db, row.user_id, user_agent)
    row.revoked = True
    row.rotated_to = _sha256(new_raw)
    db.flush()
    return row.user_id, new_raw


def revoke_all_for_user(db: Session, user_id: int) -> None:
    db.query(RefreshToken).filter(RefreshToken.user_id == user_id).update({"revoked": True})
    db.flush()
