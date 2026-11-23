"""Deployment lab: roll out a bad release and see how many users it hurts under each strategy."""
from __future__ import annotations

from typing import Any, Dict, List

from .common import rng, sel, tog

KIND = "deploy"
TICKS = 60
RPS = 1000
LEVELS: List[Dict[str, Any]] = [
    {"name": "A broken release", "title": "The new version fails 8% of requests", "bad": 0.08, "load_dep": None, "human": 28,
     "brief": "Version 2 has a bug that fails 8% of the requests it serves. Without monitoring a human notices after 28 ticks. Each failed request is a hurt user.", "goal": "Hurt as few users as possible."},
    {"name": "A subtle bug", "title": "Only 1.5% of requests fail", "bad": 0.015, "load_dep": None, "human": 40,
     "brief": "A quieter bug: 1.5% of requests fail. With very little traffic on the new version you may never see enough errors to be sure.", "goal": "Detect it before most users get it."},
    {"name": "Fails only under load", "title": "Fine at 10%, broken at 100%", "bad": 0.12, "load_dep": 0.5, "human": 30,
     "brief": "Version 2 looks perfect while it serves less than half of the traffic, then overloads and fails 12% of requests. A tiny canary cannot see it.", "goal": "Catch a problem that only appears at scale."},
]


def controls(level: int) -> List[Dict[str, Any]]:
    return [sel("strategy", "Release strategy", [["all", "All at once"], ["rolling", "Rolling (10% every tick)"], ["canary", "Canary (small slice first)"], ["bluegreen", "Blue/green (switch everything, switch back)"]], "all", "How traffic moves to the new version."),
            rng("canary_pct", "Canary share", 1, 50, 1, 5, "Percent of traffic that sees the new version first.", "%"),
            rng("watch", "Watch the canary for", 1, 20, 1, 3, "Ticks to observe before expanding.", " ticks"),
            tog("auto_rollback", "Roll back automatically on errors", False, "Monitoring compares the error rate and reverts the release.")]


def public_env(level: int) -> Dict[str, Any]:
    e = LEVELS[level]
    return {"ticks": TICKS, "rps": RPS, "bad": e["bad"], "human": e["human"]}


def run(env: Dict[str, Any], s: Dict[str, Any]) -> Dict[str, Any]:
    start = 5
    frac, errs_seen, hurt, state = 0.0, 0.0, 0.0, "pre"
    rolled_back_at = None
    frames: List[Dict[str, Any]] = []
    watch_end = None
    for t in range(TICKS):
        if state == "pre" and t >= start:
            state = "rolling"
            watch_end = t + (s["watch"] if s["strategy"] == "canary" else 0)
        target = 0.0
        if state == "rolling":
            if s["strategy"] == "all" or s["strategy"] == "bluegreen":
                target = 1.0
            elif s["strategy"] == "rolling":
                target = min(1.0, (t - start + 1) * 0.1)
            else:
                target = s["canary_pct"] / 100.0 if t < watch_end else 1.0
        if state == "rolled_back":
            target = 0.0
        frac = target
        rate = env["bad"] if (env["load_dep"] is None or frac >= env["load_dep"]) else 0.0
        failed = RPS * frac * rate
        hurt += failed
        errs_seen += failed
        if state == "rolling" and frac > 0:
            threshold = 25                               # enough errors to be statistically sure it is not noise
            detected = s["auto_rollback"] and errs_seen >= threshold
            human = (t - start) >= env["human"]
            if detected or human:
                state, rolled_back_at = "rolled_back", t
        frames.append({"t": t, "frac": round(frac, 3), "failed": round(failed, 1), "hurt": round(hurt), "state": state})
    full_at = next((f["t"] for f in frames if f["frac"] >= 1.0), None)
    stats = {"hurt": round(hurt), "peak_exposure": max(f["frac"] for f in frames), "rolled_back_at": rolled_back_at, "completed": full_at is not None and rolled_back_at is None,
             "share_hurt": round(hurt / (RPS * (TICKS - start)), 3)}
    return {"frames": frames, "stats": stats, "insights": insights(env, s, stats)}


def insights(env: Dict[str, Any], s: Dict[str, Any], st: Dict[str, Any]) -> List[str]:
    out = [f"The bad release failed {st['hurt']:,} requests. At its widest it served {st['peak_exposure'] * 100:.0f}% of users."]
    if st["rolled_back_at"] is None:
        out.append("Nothing rolled the release back, so the bug stayed live until the end.")
    elif not s["auto_rollback"]:
        out.append("Only a person noticing the graphs rolled it back, which took a long time. Automatic rollback reacts in a few ticks.")
    if s["strategy"] == "all":
        out.append("Shipping to everyone at once means every user sees the bug before anyone can react.")
    if s["strategy"] == "canary" and s["canary_pct"] < 5 and env["bad"] < 0.03:
        out.append("A 1-2% canary sees too few requests to tell a small error rate from noise. Use a larger slice or watch longer.")
    if env["load_dep"] is not None and st["peak_exposure"] >= env["load_dep"]:
        out.append("The bug only shows up once the new version carries a large share of the load. A canary that stays small never sees it, so expand in steps and keep watching.")
    if s["strategy"] == "bluegreen":
        out.append("Blue/green switches everyone at once, so the damage is fast, but switching back is instant.")
    return out


def badness(st: Dict[str, Any], env: Dict[str, Any]) -> float:
    return st["hurt"] / 100.0 + (0 if st["completed"] or env["bad"] > 0 else 0)
