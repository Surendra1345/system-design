"""
Game endpoints. Playing is open to everyone. Saving a result needs an account, and the server
always recomputes the score from what the player did, so claimed scores are ignored.

Every game has several levels. Pass ?level=0, 1, 2 ... (0 is the easiest, which is the default).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import content
from ..db import get_db
from ..deps import ai_allowed, ai_user, current_user, optional_user
from ..models import User
from ..services import ai, progress as svc
from ..sim import builder, incident as inc_sim, interview as iv_sim, labs

router = APIRouter(prefix="/api/games", tags=["games"])
Level = Query(0, ge=0, le=9, description="Level number, starting at 0")


def _need(lesson_id: str, kind: str, level: int) -> Dict[str, Any]:
    if content.game_type(lesson_id) != kind:
        raise HTTPException(404, "This lesson has no %s game." % kind)
    levels = content.levels_of(lesson_id)
    if level >= len(levels):
        raise HTTPException(404, "This game has only %d levels." % len(levels))
    return levels[level]


def _save(db: Session, user: User, lesson_id: str, level: int, stars: int, score: float) -> int:
    gained = svc.save_level(db, user, lesson_id, level, stars, score)
    db.commit()
    return gained


def _meta(lesson_id: str, level: int) -> Dict[str, Any]:
    return {"level": level, "levels": content.level_summaries(lesson_id)}


@router.get("/{lesson_id}/levels")
def list_levels(lesson_id: str):
    levels = content.level_summaries(lesson_id)
    if not levels:
        raise HTTPException(404, "This lesson has no game.")
    return {"type": content.game_type(lesson_id), "levels": levels}


# ------------------------------------------------------------------ architecture builder
class DesignBody(BaseModel):
    nodes: List[Dict[str, Any]] = Field(default_factory=list, max_length=40)
    edges: List[Dict[str, Any]] = Field(default_factory=list, max_length=120)


@router.get("/{lesson_id}/builder")
def builder_level(lesson_id: str, level: int = Level):
    sc = _need(lesson_id, "builder", level)
    peak = max(sum(v for k, v in s[2].items() if k != "abuse") for s in sc["traffic"])
    return {
        "title": sc["title"], "brief": sc["brief"], "budget": sc["budget"], "par": sc["par"], "ticks": sc["ticks"],
        "available": sc["avail"], "base_servers": int((sc.get("start") or {}).get("server", 1)),
        "traffic": [{"from": s[0], "to": s[1], **s[2]} for s in sc["traffic"]],
        "peak": round(peak), "costs": dict(builder.COST), "name": sc.get("name", "Level %d" % (level + 1)), **_meta(lesson_id, level),
    }


@router.post("/{lesson_id}/builder/simulate")
def builder_simulate(lesson_id: str, body: DesignBody, level: int = Level):
    """Run a load test on a design. Nothing is saved, so players can iterate freely."""
    return builder.simulate(_need(lesson_id, "builder", level), body.model_dump())


@router.post("/{lesson_id}/builder/submit")
def builder_submit(lesson_id: str, body: DesignBody, level: int = Level, user: User = Depends(current_user), db: Session = Depends(get_db)):
    sim = builder.simulate(_need(lesson_id, "builder", level), body.model_dump())
    stars, score = sim["result"]["stars"], round(sim["result"]["success"] * 100, 1)
    gained = _save(db, user, lesson_id, level, stars, score)
    return {"result": sim["result"], "valid": sim["valid"], "errors": sim["errors"], "xpGained": gained, "user": svc.user_view(user)}


@router.post("/{lesson_id}/builder/review")
def builder_review(lesson_id: str, body: DesignBody, level: int = Level, user: User = Depends(ai_user)):
    """An AI engineer reviews the design after a test."""
    sc = _need(lesson_id, "builder", level)
    sim = builder.simulate(sc, body.model_dump())
    if not sim["valid"]:
        raise HTTPException(400, "Fix the design first: " + " ".join(sim["errors"]))
    try:
        return {"review": ai.review_design(sc, body.model_dump(), sim)}
    except ai.AIUnavailable as e:
        raise HTTPException(503, str(e))
    except ai.AIError as e:
        raise HTTPException(502, str(e))


# ------------------------------------------------------------------ concept labs
class LabBody(BaseModel):
    settings: Dict[str, Any] = Field(default_factory=dict)


@router.get("/{lesson_id}/lab")
def lab_level(lesson_id: str, level: int = Level):
    _need(lesson_id, "lab", level)
    return {**labs.level_info(lesson_id, level), **_meta(lesson_id, level)}


@router.post("/{lesson_id}/lab/simulate")
def lab_simulate(lesson_id: str, body: LabBody, level: int = Level):
    """Run the lab with the player's settings. Nothing is saved, so players can experiment freely."""
    _need(lesson_id, "lab", level)
    return labs.run_level(lesson_id, level, body.settings)


@router.post("/{lesson_id}/lab/submit")
def lab_submit(lesson_id: str, body: LabBody, level: int = Level, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _need(lesson_id, "lab", level)
    res = labs.run_level(lesson_id, level, body.settings)
    gained = _save(db, user, lesson_id, level, res["stars"], max(0.0, 100 - res["badness"]))
    return {"stars": res["stars"], "badness": res["badness"], "stats": res["stats"], "insights": res["insights"], "xpGained": gained, "user": svc.user_view(user)}


# ------------------------------------------------------------------ incident terminal
class IncidentStep(BaseModel):
    events: List[Dict[str, Any]] = Field(default_factory=list, max_length=60)
    input: str = Field("", max_length=300)


HELP = ("Commands: logs, metrics, traces, deploys, deps. Each one costs a minute.\n"
        "To fix something, say what you would do in your own words, for example: roll back the last deploy.\n"
        "Every move costs a minute while customers see errors.")


@router.get("/{lesson_id}/incident")
def incident_start(lesson_id: str, level: int = Level):
    data = _need(lesson_id, "incident", level)
    return {"title": data["title"], "brief": data["brief"], "max": data.get("max", 12), "start": data.get("start", 60), "help": HELP,
            "fixes_needed": len(data["need"]), "name": data.get("name", "Level %d" % (level + 1)), **_meta(lesson_id, level)}


@router.post("/{lesson_id}/incident/step")
def incident_step(lesson_id: str, body: IncidentStep, level: int = Level, user: Optional[User] = Depends(optional_user)):
    data = _need(lesson_id, "incident", level)
    inc = inc_sim.replay(data, body.events)
    if inc.over:
        return {"output": "This incident is over.", "event": None, "state": inc.public_state(), "kind": "over"}
    kind, ident, note = inc_sim.parse_command(inc, body.input)
    # Free text is best understood by the language model. The built-in matcher is the fallback when AI is off,
    # the learner is a guest, the hourly AI limit is reached, or the AI service fails.
    if kind in ("act", "unknown") and note is None and user is not None and ai.available() and ai_allowed(user):
        try:
            chosen = ai.choose_action(data["acts"], body.input)
            kind, ident = ("act", chosen) if chosen else ("unknown", None)
        except (ai.AIError, ai.AIUnavailable):
            pass
    if kind == "help":
        return {"output": HELP, "event": None, "state": inc.public_state(), "kind": "help"}
    if kind == "inv":
        r = inc.investigate(ident)
        return {"output": r["text"], "event": {"k": "inv", "id": ident}, "state": inc.public_state(), "kind": "inv", "label": ident}
    if kind == "act":
        r = inc.act(ident)
        return {"output": r["msg"], "event": {"k": "act", "id": ident}, "state": inc.public_state(), "kind": r["kind"], "label": r["label"]}
    return {"output": note or "I did not understand that. Try something like 'roll back the deploy', or type help.",
            "event": None, "state": inc.public_state(), "kind": "unknown"}


class IncidentSubmit(BaseModel):
    events: List[Dict[str, Any]] = Field(default_factory=list, max_length=60)


@router.post("/{lesson_id}/incident/submit")
def incident_submit(lesson_id: str, body: IncidentSubmit, level: int = Level, user: User = Depends(current_user), db: Session = Depends(get_db)):
    data = _need(lesson_id, "incident", level)
    res = inc_sim.replay(data, body.events).result()
    gained = _save(db, user, lesson_id, level, res["stars"], max(0, 100 - res["minutes"] * 5)) if res["resolved"] else 0
    out: Dict[str, Any] = {"result": res, "xpGained": gained, "user": svc.user_view(user), "learn": data["learn"]}
    if not res["resolved"]:
        out["fix"] = [a[2] for a in data["acts"] if a[0] in data["need"]]
    return out


# ------------------------------------------------------------------ design interview
class InterviewAnswer(BaseModel):
    answer: str = Field(..., min_length=20, max_length=4000)


@router.get("/{lesson_id}/interview")
def interview_get(lesson_id: str, level: int = Level):
    data = _need(lesson_id, "interview", level)
    return {**iv_sim.public_view(data), "ai": ai.available(), "name": data.get("name", "Level %d" % (level + 1)), **_meta(lesson_id, level)}


@router.post("/{lesson_id}/interview/submit")
def interview_submit(lesson_id: str, body: InterviewAnswer, level: int = Level, user: User = Depends(current_user), db: Session = Depends(get_db)):
    data = _need(lesson_id, "interview", level)
    graded: Optional[Dict[str, Any]] = None
    if ai.available() and ai_allowed(user):
        try:
            raw = ai.grade_interview(data, body.answer)
            if raw and isinstance(raw.get("points"), list):
                graded = iv_sim.grade_from_model(data, raw["points"], str(raw.get("feedback", "")))
        except (ai.AIError, ai.AIUnavailable):
            graded = None
    if graded is None:
        graded = iv_sim.grade_with_keywords(data, body.answer)
    gained = _save(db, user, lesson_id, level, graded["stars"], graded["score"])
    return {**graded, "xpGained": gained, "user": svc.user_view(user)}
