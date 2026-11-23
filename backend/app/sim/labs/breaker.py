"""Resilience lab: a dependency gets slow or fails. Timeouts, retries and a circuit breaker decide whether you survive it."""
from __future__ import annotations

import math
from typing import Any, Dict, List

from .common import mulberry32, percentile, rng, sel, tog

KIND = "breaker"
POOL = 20
LEVELS: List[Dict[str, Any]] = [
    {"name": "Slow dependency", "title": "The payment service gets slow", "seed": 1, "ticks": 60, "rate": 6, "inc": [15, 40], "mode": "slow", "cap": 30,
     "brief": "Your checkout calls a payment service. From tick 15 to 40 it answers after 9 ticks instead of 1. Each waiting call holds one of your 20 worker threads.", "goal": "Keep checkout working while the service is slow."},
    {"name": "Failing dependency", "title": "The service throws errors", "seed": 2, "ticks": 60, "rate": 6, "inc": [15, 40], "mode": "errors", "cap": 30,
     "brief": "Between tick 15 and 40 about 70% of calls to the service fail. Some failures are brief and worth retrying, but a long outage is not.", "goal": "Recover quickly without hammering a broken service."},
    {"name": "Retry storm", "title": "Retries make the outage worse", "seed": 3, "ticks": 60, "rate": 10, "inc": [15, 40], "mode": "storm", "cap": 12,
     "brief": "The service can only handle 12 calls a tick, and during the incident only 4. Every retry adds more load to a service that is already struggling.", "goal": "Do not turn a small outage into a big one."},
]


def controls(level: int) -> List[Dict[str, Any]]:
    return [rng("timeout", "Timeout", 1, 10, 1, 10, "How long to wait for one call before giving up.", " ticks"),
            rng("retries", "Retries", 0, 5, 1, 3, "How many more times to try after a failure."),
            sel("backoff", "Wait between retries", [["none", "No wait"], ["exp", "Wait longer each time"], ["jitter", "Wait longer, plus randomness"]], "none", "Backoff spreads retries out in time."),
            tog("breaker", "Circuit breaker", False, "After repeated failures, stop calling the service for a while and fail fast."),
            rng("threshold", "Breaker opens after", 1, 20, 1, 5, "Consecutive failures before the breaker opens.", " failures"),
            rng("open_ticks", "Breaker stays open", 1, 20, 1, 5, "Then it lets one test call through.", " ticks"),
            tog("fallback", "Fallback answer", False, "When the call cannot be made, show a safe default instead of an error.")]


def public_env(level: int) -> Dict[str, Any]:
    e = LEVELS[level]
    return {"ticks": e["ticks"], "inc": e["inc"], "pool": POOL, "mode": e["mode"]}


def run(env: Dict[str, Any], s: Dict[str, Any]) -> Dict[str, Any]:
    rg = mulberry32(env["seed"])
    inflight: List[Dict[str, Any]] = []      # attempts holding a thread
    waiting: List[Dict[str, Any]] = []       # requests waiting to retry
    state, fails, opened_at, probing = "closed", 0, 0, False
    outcome = {"ok": 0, "degraded": 0, "failed": 0}
    lat: List[float] = []
    calls = 0
    max_threads = 0
    nid = 0
    frames: List[Dict[str, Any]] = []
    a, b = env["inc"]

    def finish(r: Dict[str, Any], t: int, kind: str) -> None:
        outcome[kind] += 1
        lat.append(t - r["arr"] + 1)

    def delay(k: int) -> int:
        if s["backoff"] == "none":
            return 1
        base = 2 ** k
        return base if s["backoff"] == "exp" else 1 + int(rg() * (base + 1))

    def start(r: Dict[str, Any], t: int, attempts_now: List[int]) -> None:
        nonlocal state, opened_at, probing, calls
        if s["breaker"] and state == "open":
            if t - opened_at >= s["open_ticks"]:
                state, probing = "half", False
            else:
                finish(r, t, "degraded" if s["fallback"] else "failed")
                return
        if s["breaker"] and state == "half":
            if probing:
                finish(r, t, "degraded" if s["fallback"] else "failed")
                return
            probing = True
        if len(inflight) >= POOL:
            finish(r, t, "degraded" if s["fallback"] else "failed")      # no free thread
            return
        calls += 1
        attempts_now[0] += 1
        incident = a <= t < b
        L, err = 1, False
        if incident and env["mode"] == "slow":
            L = 9
        elif incident and env["mode"] == "errors":
            err = rg() < 0.7
        cap = env["cap"] if not incident else (env["cap"] if env["mode"] != "storm" else 4)
        if attempts_now[0] > cap:
            L += 3 + (attempts_now[0] - cap) // 2           # overloaded service answers slowly
        if env["mode"] == "storm" and incident and attempts_now[0] > cap:
            err = rg() < 0.65
        dur = min(L, s["timeout"])
        ok = (L <= s["timeout"]) and not err
        inflight.append({"r": r, "end": t + dur, "ok": ok})

    for t in range(env["ticks"]):
        attempts_now = [0]
        for w in [w for w in waiting if w["at"] <= t]:
            waiting.remove(w)
            start(w["r"], t, attempts_now)
        for _ in range(env["rate"]):
            nid += 1
            start({"id": nid, "arr": t, "tries": 0}, t, attempts_now)
        max_threads = max(max_threads, len(inflight))
        done_now = [x for x in inflight if x["end"] <= t + 1]
        for x in done_now:
            inflight.remove(x)
            r = x["r"]
            if x["ok"]:
                fails = 0
                if state == "half":
                    state = "closed"
                finish(r, x["end"] - 1, "ok")
            else:
                fails += 1
                if s["breaker"] and (state == "half" or (state == "closed" and fails >= s["threshold"])):
                    state, opened_at, probing = "open", x["end"], False
                if r["tries"] < s["retries"]:
                    r["tries"] += 1
                    waiting.append({"r": r, "at": x["end"] + delay(r["tries"])})
                else:
                    finish(r, x["end"] - 1, "degraded" if s["fallback"] else "failed")
        frames.append({"t": t, "threads": len(inflight), "state": state, "ok": outcome["ok"], "degraded": outcome["degraded"], "failed": outcome["failed"],
                       "incident": a <= t < b, "calls": attempts_now[0], "waiting": len(waiting)})
    total = max(1, sum(outcome.values()))
    stats = {"ok": outcome["ok"], "degraded": outcome["degraded"], "failed": outcome["failed"], "fail_frac": round(outcome["failed"] / total, 3),
             "degraded_frac": round(outcome["degraded"] / total, 3), "p95": percentile(lat, 95), "max_threads": max_threads, "calls": calls, "pool": POOL}
    return {"frames": frames, "stats": stats, "insights": insights(env, s, stats)}


def insights(env: Dict[str, Any], s: Dict[str, Any], st: Dict[str, Any]) -> List[str]:
    out = [f"{st['ok']} requests succeeded, {st['degraded']} got a fallback answer and {st['failed']} failed. The slowest 5% took {st['p95']:.0f} ticks."]
    if st["max_threads"] >= st["pool"] - 1:
        out.append("The thread pool ran out. Threads stuck waiting on the slow service left none for new requests, so even healthy work failed. Shorter timeouts or a breaker free them.")
    if s["retries"] > 1 and s["backoff"] == "none" and env["mode"] != "slow":
        out.append("Retrying immediately sends the same load again to a service that is already struggling. Wait longer between retries, and add randomness so clients do not retry together.")
    if not s["breaker"] and st["failed"] > 40:
        out.append("Without a circuit breaker you keep calling a service that is clearly down. A breaker fails fast and gives it time to recover.")
    if not s["fallback"] and st["failed"] > 0:
        out.append("A fallback answer (a cached value, a default, a message) turns many errors into a degraded but working page.")
    if s["breaker"] and s["open_ticks"] > 12:
        out.append("The breaker stays open for a long time, so you may keep failing after the service has recovered.")
    return out


def badness(st: Dict[str, Any], env: Dict[str, Any]) -> float:
    return 100 * st["fail_frac"] + 30 * st["degraded_frac"] + 0.5 * st["p95"]
