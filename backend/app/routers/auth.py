from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import current_user, limit_login
from ..models import SessionToken, User
from ..security import hash_password, hash_token, new_token, verify_password
from ..services.progress import user_view

router = APIRouter(prefix="/api/auth", tags=["auth"])
USERNAME = re.compile(r"^[A-Za-z0-9_]{3,24}$")


class Credentials(BaseModel):
    username: str
    password: str


def _session(db: Session, user: User) -> dict:
    token = new_token()
    expires = datetime.now(timezone.utc) + timedelta(days=get_settings().session_days)
    db.add(SessionToken(token_hash=hash_token(token), user_id=user.id, expires_at=expires))
    db.commit()
    return {"token": token, "user": user_view(user)}


@router.post("/register", status_code=201, dependencies=[Depends(limit_login)])
def register(body: Credentials, db: Session = Depends(get_db)):
    if not USERNAME.match(body.username):
        raise HTTPException(400, "Username must be 3 to 24 letters, numbers or underscores.")
    if not 8 <= len(body.password) <= 128:
        raise HTTPException(400, "Password must be 8 to 128 characters.")
    if db.scalar(select(User.id).where(func.lower(User.username) == body.username.lower())):
        raise HTTPException(409, "That username is taken.")
    salt, digest = hash_password(body.password)
    user = User(username=body.username, salt=salt, password_hash=digest)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "That username is taken.")
    return _session(db, user)


@router.post("/login", dependencies=[Depends(limit_login)])
def login(body: Credentials, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.username) == body.username.lower()))
    # Always do the hashing work so timing does not reveal whether the user exists.
    ok = verify_password(body.password, user.salt if user else "x" * 32, user.password_hash if user else "0" * 128)
    if not user or not ok:
        raise HTTPException(401, "Wrong username or password.")
    return _session(db, user)


@router.post("/logout")
def logout(authorization: Optional[str] = Header(None), user: User = Depends(current_user), db: Session = Depends(get_db)):
    sess = db.get(SessionToken, hash_token((authorization or "")[7:].strip()))
    if sess is not None:
        db.delete(sess)
        db.commit()
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return user_view(user)
