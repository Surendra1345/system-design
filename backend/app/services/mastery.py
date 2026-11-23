"""Concept mastery from evidence, not from stars alone.

A concept (one lesson) is *mastered* when it has been read and every level of its game has two or more stars, meaning the learner coped
with the harder variations too. It is *shaky* when some levels are strong and others are weak, which is the sign of having memorised
one situation. It is *learning* once started, and *new* before that.
"""
from __future__ import annotations

from typing import Dict, List, Optional

MASTERED, SHAKY, LEARNING, NEW = "mastered", "shaky", "learning", "new"


def status(read: bool, level_stars: List[int]) -> str:
    if not level_stars:                          # a lesson without a game: reading is the only evidence
        return MASTERED if read else NEW
    strong = [s >= 2 for s in level_stars]
    if all(strong) and read:
        return MASTERED
    if any(strong) and not all(strong):
        return SHAKY
    if read or any(s > 0 for s in level_stars):
        return LEARNING
    return NEW


def weakest_level(level_stars: List[int]) -> Optional[int]:
    return min(range(len(level_stars)), key=lambda i: level_stars[i]) if level_stars else None


def summary(statuses: Dict[str, str]) -> Dict[str, int]:
    out = {MASTERED: 0, SHAKY: 0, LEARNING: 0, NEW: 0}
    for s in statuses.values():
        out[s] += 1
    return out
