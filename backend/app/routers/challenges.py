"""Unknown Problem Challenges and the mastery dashboard."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import content, rules
from ..db import get_db
from ..deps import ai_allowed, current_user, optional_user
from ..models import ChallengeAttempt, LessonProgress, LevelProgress, User
from ..services import ai, progress as svc
from ..sim import challenge as ch, interview as iv_sim

router = APIRouter(prefix="/api", tags=["challenges"])
ORDER = [("feed", "Easier"), ("flashsale", "Medium"), ("bank", "Harder")]


class Attempt(BaseModel):
    seed: int = Field(0, ge=0, le=999999)
    diagnosis: Dict[str, str] = Field(default_factory=dict)
    measures: List[str] = Field(default_factory=list, max_length=20)
    defense: Optional[str] = Field(None, max_length=3000)


def _tpl(tid: str) -> None:
    if tid not in ch.TEMPLATES:
        raise HTTPException(404, "Unknown challenge.")


def _best(db: Session, user_id: int) -> Dict[str, int]:
    rows = db.execute(select(ChallengeAttempt.template, func.max(ChallengeAttempt.stars)).where(ChallengeAttempt.user_id == user_id).group_by(ChallengeAttempt.template)).all()
    return {t: int(s or 0) for t, s in rows}


@router.get("/challenges")
def list_challenges(user: Optional[User] = Depends(optional_user), db: Session = Depends(get_db)):
    best = _best(db, user.id) if user else {}
    return [{"id": t, "title": ch.TEMPLATES[t]["title"], "blurb": ch.TEMPLATES[t]["blurb"], "level": lv, "best": best.get(t, 0)} for t, lv in ORDER]


@router.get("/challenges/{tid}")
def get_challenge(tid: str, seed: int = Query(0, ge=0, le=999999)):
    _tpl(tid)
    return ch.public(tid, seed)


@router.post("/challenges/{tid}/simulate")
def simulate(tid: str, body: Attempt):
    _tpl(tid)
    return ch.run(tid, body.seed, body.diagnosis, body.measures)


@router.post("/challenges/{tid}/submit")
def submit(tid: str, body: Attempt, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _tpl(tid)
    res = ch.run(tid, body.seed, body.diagnosis, body.measures)
    defend: Optional[Dict[str, Any]] = None
    if body.defense and len(body.defense.strip()) >= 20:
        data = ch.defend_data(tid, res)
        if ai.available() and ai_allowed(user):
            try:
                raw = ai.grade_interview(data, body.defense)
                if raw and isinstance(raw.get("points"), list):
                    defend = iv_sim.grade_from_model(data, raw["points"], str(raw.get("feedback", "")))
            except (ai.AIError, ai.AIUnavailable):
                defend = None
        if defend is None:
            defend = iv_sim.grade_with_keywords(data, body.defense)
    before = _best(db, user.id).get(tid, 0)
    db.add(ChallengeAttempt(user_id=user.id, template=tid, seed=body.seed, stars=res["stars"], score=res["score"], diag_right=res["diag_right"], diag_total=res["total"],
                            defended=bool(defend and defend["stars"] >= 2)))
    gained = svc.award(db, user, "challenge", tid, max(0, res["stars"] - before) * rules.XP_PER_STAR)
    db.commit()
    return {**res, "defense": defend, "xpGained": gained, "user": svc.user_view(user)}


# ------------------------------------------------------------------ mastery
def _max_stars(kinds: set) -> Dict[str, int]:
    return {l["id"]: len(content.levels_of(l["id"])) * 3 for l in content.lessons_doc()["lessons"] if content.game_type(l["id"]) in kinds}


@router.get("/mastery")
def mastery(user: User = Depends(current_user), db: Session = Depends(get_db)):
    lessons = [l["id"] for l in content.lessons_doc()["lessons"]]
    read = {r.lesson_id for r in db.scalars(select(LessonProgress).where(LessonProgress.user_id == user.id, LessonProgress.read_done.is_(True)))}
    stars: Dict[str, int] = {}
    for r in db.scalars(select(LevelProgress).where(LevelProgress.user_id == user.id)):
        stars[r.lesson_id] = stars.get(r.lesson_id, 0) + r.stars
    att = list(db.scalars(select(ChallengeAttempt).where(ChallengeAttempt.user_id == user.id)))

    def share(kinds: set) -> float:
        mx = _max_stars(kinds)
        return sum(min(stars.get(k, 0), v) for k, v in mx.items()) / max(1, sum(mx.values()))

    understanding = len(read) / max(1, len(lessons))
    practice = share({"lab", "builder"})
    incident = share({"incident"})
    diag_acc = sum(a.diag_right for a in att) / max(1, sum(a.diag_total for a in att)) if att else 0.0
    diagnosis = (incident + diag_acc) / 2 if att else incident
    variations = min(1.0, len({(a.template, a.seed) for a in att if a.stars >= 2}) / 6.0)
    best = _best(db, user.id)
    design = (share({"builder", "interview"}) + (sum(best.values()) / (3 * len(ch.TEMPLATES)))) / 2
    dims = [
        {"id": "understanding", "name": "Concept understanding", "pct": round(100 * understanding), "detail": f"{len(read)} of {len(lessons)} lessons read", "hint": "Read the primer and theory, then mark lessons as read."},
        {"id": "practice", "name": "Practical application", "pct": round(100 * practice), "detail": "Stars earned in labs and builders", "hint": "Play the labs you have not tried, and aim for three stars."},
        {"id": "variations", "name": "Problem variations", "pct": round(100 * variations), "detail": f"{len({(a.template, a.seed) for a in att if a.stars >= 2})} of 6 different challenge variations solved", "hint": "Press New variation on a challenge: the numbers change, and so can the best answer."},
        {"id": "diagnosis", "name": "Failure diagnosis", "pct": round(100 * diagnosis), "detail": "Incident games and challenge diagnoses", "hint": "Play the live-outage lessons and diagnose challenge symptoms before choosing fixes."},
        {"id": "design", "name": "Independent design", "pct": round(100 * design), "detail": "Builders, interviews and challenges", "hint": "Try a challenge without hints, then explain your choices."},
    ]
    weakest = min(dims, key=lambda d: d["pct"])
    labs = [l for l in lessons if content.game_type(l) in ("lab", "incident") and stars.get(l, 0) == 0][:3]
    return {"dimensions": dims, "weakest": weakest, "challenges": [{"id": t, "title": ch.TEMPLATES[t]["title"], "best": best.get(t, 0)} for t, _ in ORDER], "attempts": len(att),
            "next": [{"id": l, "title": content.lesson_index()[l]["title"]} for l in labs]}
