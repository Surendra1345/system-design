from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from .. import content
from ..db import get_db
from ..models import User
from ..rules import RANKS, rank_index

router = APIRouter(prefix="/api", tags=["content"])


@router.get("/catalog")
def catalog():
    """Tracks and a light list of lessons. Lesson bodies are fetched one at a time."""
    doc = content.lessons_doc()
    lessons = [{"id": l["id"], "track": l["t"], "title": l["title"], "summary": l["sum"],
                "game": content.game_type(l["id"]), "levels": len(content.levels_of(l["id"])), "projects": l.get("projects", False)} for l in doc["lessons"]]
    return {"tracks": doc["tracks"], "lessons": lessons}


@router.get("/lessons/{lesson_id}")
def lesson(lesson_id: str):
    l = content.lesson_index().get(lesson_id)
    if not l:
        raise HTTPException(404, "Unknown lesson.")
    out = dict(l)
    out["game"] = content.game_type(lesson_id)
    out["explain"] = content.explain().get(lesson_id)
    out["levels"] = content.level_summaries(lesson_id)
    out["deep"] = content.deep().get(lesson_id)
    oc = content.outcomes().get(lesson_id)
    if oc:
        idx = content.lesson_index()
        out["outcomes"] = {"outcomes": oc["outcomes"], "variations": oc["variations"], "prereqs": [{"id": p, "title": idx[p]["title"]} for p in oc["prereqs"]]}
    st = content.stages().get(lesson_id)
    if st:
        out["stages"] = st["stages"]
        out["tutor_prompts"] = st["tutor"]
    if l.get("projects"):
        out["project_list"] = content.lessons_doc()["projects"]
    return out


@router.get("/breaks")
def breaks():
    """Every 'what breaks' note, for the edge-case handbook."""
    return [{"lesson": l["id"], "title": l["title"], "items": l["breaks"]} for l in content.lessons_doc()["lessons"]]


@router.get("/leaderboard")
def leaderboard(db: Session = Depends(get_db)):
    rows = db.execute(select(User.username, User.xp).order_by(User.xp.desc(), User.id.asc()).limit(20)).all()
    return [{"rank": i + 1, "username": u, "xp": x, "title": RANKS[rank_index(x)]} for i, (u, x) in enumerate(rows)]
