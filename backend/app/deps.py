from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import SessionToken, User
from .security import TokenBucket, hash_token

# One bucket per client address for logins, one per user for AI calls (they cost money).
login_limiter = TokenBucket(capacity=10, per_second=0.2)
_ai_limiter: Optional[TokenBucket] = None


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def optional_user(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)) -> Optional[User]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    sess = db.get(SessionToken, hash_token(authorization[7:].strip()))
    if sess is None or _aware(sess.expires_at) <= datetime.now(timezone.utc):
        return None
    return db.get(User, sess.user_id)


def current_user(user: Optional[User] = Depends(optional_user)) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in to do that.")
    return user


def _ai_bucket() -> TokenBucket:
    global _ai_limiter
    if _ai_limiter is None:
        n = get_settings().ai_calls_per_hour
        _ai_limiter = TokenBucket(capacity=n, per_second=n / 3600)
    return _ai_limiter


def ai_allowed(user: User) -> bool:
    """True if this learner still has AI calls left this hour (and uses one)."""
    return _ai_bucket().allow(str(user.id))


def ai_user(user: User = Depends(current_user)) -> User:
    if not ai_allowed(user):
        raise HTTPException(status_code=429, detail="You have used a lot of AI help this hour. Please try again later.")
    return user


def limit_login(request: Request) -> None:
    key = request.client.host if request.client else "unknown"
    if not login_limiter.allow(key):
        raise HTTPException(status_code=429, detail="Too many attempts. Please wait a moment.")
