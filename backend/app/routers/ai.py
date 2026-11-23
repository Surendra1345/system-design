from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import content
from ..deps import ai_user
from ..models import User
from ..services import ai

router = APIRouter(prefix="/api/ai", tags=["ai"])


class TutorBody(BaseModel):
    lesson_id: str
    question: str = Field(..., min_length=2, max_length=1500)
    history: List[Dict[str, str]] = Field(default_factory=list, max_length=12)


class PlanBody(BaseModel):
    idea: str = Field(..., min_length=10, max_length=2000)


@router.get("/status")
def status():
    return {"enabled": ai.available()}


def _run(fn, *args):
    try:
        return fn(*args)
    except ai.AIUnavailable as e:
        raise HTTPException(503, str(e))
    except ai.AIError as e:
        raise HTTPException(502, str(e))


@router.post("/tutor")
def tutor(body: TutorBody, user: User = Depends(ai_user)):
    lesson = content.lesson_index().get(body.lesson_id)
    if not lesson:
        raise HTTPException(404, "Unknown lesson.")
    answer = _run(ai.tutor, lesson["title"], content.lesson_text(body.lesson_id), body.question, body.history)
    return {"answer": answer}


@router.post("/plan")
def plan(body: PlanBody, user: User = Depends(ai_user)):
    return {"plan": _run(ai.plan, body.idea)}
