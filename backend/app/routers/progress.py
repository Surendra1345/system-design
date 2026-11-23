from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import content, rules
from ..db import get_db
from ..deps import current_user
from ..models import ProjectDone, StudyTime, User
from ..services import progress as svc

router = APIRouter(prefix="/api", tags=["progress"])


class ReadBody(BaseModel):
    done: bool


class TimeBody(BaseModel):
    targetMin: Optional[int] = Field(None, ge=0, le=100000)
    addSec: Optional[int] = Field(None, ge=0, le=4 * 3600)


class ProjectBody(BaseModel):
    done: bool


def _lesson_or_404(lesson_id: str) -> None:
    if lesson_id not in content.lesson_index():
        raise HTTPException(404, "Unknown lesson.")


@router.get("/progress")
def get_progress(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return svc.full_progress(db, user)


@router.put("/lessons/{lesson_id}/read")
def mark_read(lesson_id: str, body: ReadBody, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _lesson_or_404(lesson_id)
    row = svc.progress_row(db, user.id, lesson_id)
    row.read_done = body.done
    gained = 0
    if body.done and not svc.already_paid(db, user.id, "read", lesson_id):
        gained = svc.award(db, user, "read", lesson_id, rules.READ_XP)  # paid once, even if re-ticked
    db.commit()
    return {"xpGained": gained, "user": svc.user_view(user)}


@router.put("/time/{lesson_id}")
def set_time(lesson_id: str, body: TimeBody, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The learner decides how long to spend. We only record it."""
    _lesson_or_404(lesson_id)
    row = db.scalar(select(StudyTime).where(StudyTime.user_id == user.id, StudyTime.lesson_id == lesson_id))
    if row is None:
        row = StudyTime(user_id=user.id, lesson_id=lesson_id, spent_sec=0)
        db.add(row)
    if "targetMin" in body.model_fields_set:
        row.target_min = body.targetMin or None
    if body.addSec:
        row.spent_sec += body.addSec
    db.commit()
    return {"targetMin": row.target_min, "spentSec": row.spent_sec}


@router.put("/projects/{project_id}")
def set_project(project_id: str, body: ProjectBody, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if project_id not in content.project_ids():
        raise HTTPException(404, "Unknown project.")
    row = db.scalar(select(ProjectDone).where(ProjectDone.user_id == user.id, ProjectDone.project_id == project_id))
    gained = 0
    if body.done and row is None:
        db.add(ProjectDone(user_id=user.id, project_id=project_id))
        if not svc.already_paid(db, user.id, "project", project_id):
            gained = svc.award(db, user, "project", project_id, rules.PROJECT_XP)
    elif not body.done and row is not None:
        db.delete(row)
    db.commit()
    return {"xpGained": gained, "user": svc.user_view(user)}
