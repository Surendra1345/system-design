"""
Design interview scoring. A language model grades the answer against a rubric when one is
configured. Otherwise a keyword check gives a plain, predictable score.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

STAR_BANDS = ((0.8, 3), (0.6, 2), (0.4, 1))


def stars_for(score: float) -> int:
    for floor, stars in STAR_BANDS:
        if score >= floor:
            return stars
    return 0


def grade_with_keywords(interview: Dict[str, Any], answer: str) -> Dict[str, Any]:
    text = answer.lower()
    points: List[Dict[str, Any]] = []
    for p in interview["rubric"]:
        hit = any(k.lower() in text for k in p["keywords"])
        points.append({"id": p["id"], "point": p["point"], "hit": hit,
                       "comment": "Covered." if hit else "Not mentioned. Try to address this in your answer."})
    return _summarise(points, "Graded with a simple keyword check. Turn on the AI interviewer (set GROQ_API_KEY) for feedback on your reasoning.", "keywords")


def grade_from_model(interview: Dict[str, Any], model_points: List[Dict[str, Any]], feedback: str) -> Dict[str, Any]:
    wanted = {p["id"]: p["point"] for p in interview["rubric"]}
    seen: Dict[str, Dict[str, Any]] = {}
    for mp in model_points or []:
        pid = str(mp.get("id"))
        if pid in wanted and pid not in seen:
            seen[pid] = {"id": pid, "point": wanted[pid], "hit": bool(mp.get("hit")), "comment": str(mp.get("comment", ""))[:300]}
    points = [seen.get(pid, {"id": pid, "point": text, "hit": False, "comment": "Not mentioned."}) for pid, text in wanted.items()]
    return _summarise(points, feedback[:1500], "ai")


def _summarise(points: List[Dict[str, Any]], feedback: str, graded_by: str) -> Dict[str, Any]:
    score = sum(1 for p in points if p["hit"]) / max(1, len(points))
    return {"score": round(score * 100), "stars": stars_for(score), "points": points, "feedback": feedback, "graded_by": graded_by}


def public_view(interview: Dict[str, Any]) -> Dict[str, Any]:
    """What the player sees before answering: the prompt and what is being assessed, not the keywords."""
    return {"title": interview["title"], "prompt": interview["prompt"],
            "criteria": [p["point"] for p in interview["rubric"]], "tips": interview.get("tips", [])}
