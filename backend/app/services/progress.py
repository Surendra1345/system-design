from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import rules
from ..models import LessonProgress, LevelProgress, ProjectDone, StudyTime, User, XpEvent


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _yesterday() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")


def touch_day(user: User) -> None:
    t = today()
    if user.last_day == t:
        return
    user.streak = user.streak + 1 if user.last_day == _yesterday() else 1
    user.last_day = t


def already_paid(db: Session, user_id: int, kind: str, ref: str) -> bool:
    return db.scalar(select(XpEvent.id).where(XpEvent.user_id == user_id, XpEvent.kind == kind, XpEvent.ref == ref)) is not None


def award(db: Session, user: User, kind: str, ref: str, xp: int) -> int:
    touch_day(user)
    if xp > 0:
        db.add(XpEvent(user_id=user.id, kind=kind, ref=ref, xp=xp))
        user.xp += xp
    return xp


def user_view(user: User) -> Dict[str, object]:
    live = user.last_day in (today(), _yesterday())
    idx = rules.rank_index(user.xp)
    return {"username": user.username, "xp": user.xp, "rank": rules.RANKS[idx], "level": idx + 1, "streak": user.streak if live else 0}


def progress_row(db: Session, user_id: int, lesson_id: str) -> LessonProgress:
    row = db.scalar(select(LessonProgress).where(LessonProgress.user_id == user_id, LessonProgress.lesson_id == lesson_id))
    if row is None:
        row = LessonProgress(user_id=user_id, lesson_id=lesson_id, read_done=False, stars=0)
        db.add(row)
        db.flush()
    return row


def save_level(db: Session, user: User, lesson_id: str, level: int, stars: int, score: float) -> int:
    """Record a level result. Returns the XP earned, which is only for stars not earned before."""
    row = db.scalar(select(LevelProgress).where(LevelProgress.user_id == user.id, LevelProgress.lesson_id == lesson_id, LevelProgress.level == level))
    if row is None:
        row = LevelProgress(user_id=user.id, lesson_id=lesson_id, level=level, stars=0)
        db.add(row)
    gained = max(0, stars - row.stars) * rules.XP_PER_STAR
    row.stars = max(row.stars, stars)
    row.best_score = max(row.best_score or 0.0, score)
    db.flush()
    total = db.scalar(select(func.coalesce(func.sum(LevelProgress.stars), 0)).where(LevelProgress.user_id == user.id, LevelProgress.lesson_id == lesson_id))
    lp = progress_row(db, user.id, lesson_id)
    lp.stars = int(total or 0)
    lp.best_score = max(lp.best_score or 0.0, score)
    award(db, user, "game", "%s:%d" % (lesson_id, level), gained)
    return gained


def full_progress(db: Session, user: User) -> Dict[str, object]:
    lessons = {
        r.lesson_id: {"read": r.read_done, "stars": r.stars, "score": r.best_score}
        for r in db.scalars(select(LessonProgress).where(LessonProgress.user_id == user.id))
    }
    time = {r.lesson_id: {"targetMin": r.target_min, "spentSec": r.spent_sec}
            for r in db.scalars(select(StudyTime).where(StudyTime.user_id == user.id))}
    projects = [r.project_id for r in db.scalars(select(ProjectDone).where(ProjectDone.user_id == user.id))]
    levels: Dict[str, Dict[str, int]] = {}
    for r in db.scalars(select(LevelProgress).where(LevelProgress.user_id == user.id)):
        levels.setdefault(r.lesson_id, {})[str(r.level)] = r.stars
    return {"user": user_view(user), "lessons": lessons, "levels": levels, "time": time, "projects": projects}
