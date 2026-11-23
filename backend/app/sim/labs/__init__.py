"""Concept labs: a different hands-on simulation for each core concept."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import autoscale, breaker, cache, cap, cdn, clocks, consensus, deploy, engines, journey, lb, limiter, micro, queue, repl, shard, slo, streaming, tx
from .common import clean_settings

KINDS = {m.KIND: m for m in (lb, cache, cdn, queue, shard, limiter, breaker, autoscale, repl, tx, consensus, clocks, cap, journey, slo, deploy, streaming, engines, micro)}
LESSON_LAB = {"lb": "lb", "cache": "cache", "cdn": "cdn", "queue": "queue", "shard": "shard",
              "ratelimiter": "limiter", "resil": "breaker", "serverless": "autoscale",
              "repl": "repl", "tx": "tx", "consensus": "consensus", "clocks": "clocks", "cap": "cap",
              "journey": "journey", "slo": "slo", "deploy": "deploy", "streaming": "streaming", "engines": "engines", "micro": "micro"}
THRESHOLDS_FILE = Path(__file__).resolve().parents[2] / "content" / "lab_thresholds.json"


def thresholds() -> Dict[str, Any]:
    try:
        return json.loads(THRESHOLDS_FILE.read_text())
    except (OSError, ValueError):
        return {}


def is_lab(lesson_id: str) -> bool:
    return lesson_id in LESSON_LAB


def module(lesson_id: str):
    return KINDS[LESSON_LAB[lesson_id]]


def n_levels(lesson_id: str) -> int:
    return len(module(lesson_id).LEVELS)


def level_info(lesson_id: str, level: int) -> Dict[str, Any]:
    m = module(lesson_id)
    e = m.LEVELS[level]
    return {"kind": m.KIND, "name": e["name"], "title": e["title"], "brief": e["brief"], "goal": e["goal"], "controls": m.controls(level),
            "env": m.public_env(level), "ticks": e.get("ticks")}


def stars_for(bad: float, th: Optional[List[float]]) -> int:
    if not th:
        return 0
    return 3 if bad <= th[0] else 2 if bad <= th[1] else 1 if bad <= th[2] else 0


def run_level(lesson_id: str, level: int, raw: Dict[str, Any]) -> Dict[str, Any]:
    m = module(lesson_id)
    env = m.LEVELS[level]
    s = clean_settings(m.controls(level), raw)
    out = m.run(env, s)
    bad = float(m.badness(out["stats"], env))
    t = thresholds().get("%s:%d" % (lesson_id, level), {})
    out.update({"settings": s, "badness": round(bad, 2), "stars": stars_for(bad, t.get("stars")), "hint": t.get("solution_hint")})
    return out
