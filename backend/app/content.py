"""Lesson and game content. It lives in JSON files so editors never touch code."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

DIR = Path(__file__).parent / "content"


def _load(name: str) -> Any:
    return json.loads((DIR / name).read_text(encoding="utf-8"))


@lru_cache
def lessons_doc() -> Dict[str, Any]:
    return _load("lessons.json")


@lru_cache
def lesson_index() -> Dict[str, Dict[str, Any]]:
    return {l["id"]: l for l in lessons_doc()["lessons"]}


@lru_cache
def outcomes() -> Dict[str, Dict[str, Any]]:
    """Learning outcomes, the variations that prove mastery and the prerequisites, per lesson."""
    return _load("outcomes.json")


@lru_cache
def project_ids() -> set:
    return {p["id"] for p in lessons_doc()["projects"]}


@lru_cache
def explain() -> Dict[str, Dict[str, Any]]:
    """Plain-English notes for every lesson: what it is, why we use it, when to use it."""
    return _load("explain.json")


@lru_cache
def deep() -> Dict[str, Dict[str, Any]]:
    """Researched deep dives, one JSON file per group of lessons in content/deep/."""
    out: Dict[str, Dict[str, Any]] = {}
    for f in sorted((DIR / "deep").glob("deep_*.json")):
        out.update(json.loads(f.read_text(encoding="utf-8")))
    return out


@lru_cache
def builder_scenarios() -> Dict[str, List[Dict[str, Any]]]:
    return _load("builder.json")


@lru_cache
def incidents() -> Dict[str, List[Dict[str, Any]]]:
    return _load("incidents.json")


@lru_cache
def interviews() -> Dict[str, List[Dict[str, Any]]]:
    return _load("interviews.json")


def game_type(lesson_id: str) -> Optional[str]:
    from .sim import labs

    if labs.is_lab(lesson_id):
        return "lab"
    if lesson_id in builder_scenarios():
        return "builder"
    if lesson_id in incidents():
        return "incident"
    if lesson_id in interviews():
        return "interview"
    return None


def levels_of(lesson_id: str) -> List[Dict[str, Any]]:
    """Every level of a lesson's game, easiest first. Empty for lessons without a game."""
    kind = game_type(lesson_id)
    if kind is None:
        return []
    if kind == "lab":
        from .sim import labs

        return labs.module(lesson_id).LEVELS
    return {"builder": builder_scenarios, "incident": incidents, "interview": interviews}[kind]()[lesson_id]


def level_summaries(lesson_id: str) -> List[Dict[str, Any]]:
    return [{"index": i, "name": lv.get("name", "Level %d" % (i + 1)), "title": lv["title"]} for i, lv in enumerate(levels_of(lesson_id))]


def lesson_text(lesson_id: str, limit: int = 6000) -> str:
    """Plain text of a lesson, used to ground the AI tutor."""
    import re

    l = lesson_index()[lesson_id]
    parts = [l["title"], l["sum"]]
    for s in l["sec"]:
        parts.append(s["h"] + ": " + s["b"])
    parts.append("What breaks: " + " ".join(l["breaks"]))
    text = re.sub(r"<[^>]+>", " ", " ".join(parts))
    return re.sub(r"\s+", " ", text)[:limit]
