from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import optional_user
from ..models import Feedback, User
from ..security import TokenBucket

router = APIRouter(prefix="/api/feedback", tags=["pilot"])

# Feedback is open to anyone with the link, so one address cannot flood the table.
_limiter = TokenBucket(capacity=10, per_second=0.05)


class FeedbackBody(BaseModel):
    page: str = Field(min_length=1, max_length=120, pattern=r"^/[A-Za-z0-9/_\-]*$")
    kind: Literal["clear", "unclear", "confusing", "bug", "idea", "liked"]
    rating: Optional[int] = Field(None, ge=1, le=5)
    message: str = Field("", max_length=1000)


@router.post("", status_code=201)
def send_feedback(body: FeedbackBody, request: Request, user: Optional[User] = Depends(optional_user),
                  db: Session = Depends(get_db)):
    who = request.client.host if request.client else "unknown"
    if not _limiter.allow(who):
        raise HTTPException(429, "Thanks! Please wait a moment before sending more.")
    db.add(Feedback(user_id=user.id if user else None, page=body.page, kind=body.kind,
                    rating=body.rating, message=body.message.strip()))
    db.commit()
    return {"ok": True}
