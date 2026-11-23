"""Microservices lab: every service you add to the request path multiplies the chance something fails."""
from __future__ import annotations

from typing import Any, Dict, List

from .common import mulberry32, rng, tog

KIND = "micro"
REQS = 4000
LEVELS: List[Dict[str, Any]] = [
    {"name": "Checkout chain", "title": "Five services in a row", "seed": 1, "services": [["gateway", 99.9, True], ["cart", 99.9, True], ["pricing", 99.9, True], ["payments", 99.9, True], ["email", 99.9, False]], "hop": 8, "slow": None,
     "brief": "A checkout request calls five services one after another, each 99.9% available. The email service is nice to have, not essential.", "goal": "Get checkout as reliable as you can without changing a single service."},
    {"name": "Shaky dependencies", "title": "Eight services, some weaker", "seed": 2, "services": [["gateway", 99.95, True], ["auth", 99.9, True], ["catalogue", 99.5, True], ["recommendations", 98.0, False], ["reviews", 98.5, False], ["pricing", 99.9, True], ["payments", 99.9, True], ["notifications", 99.0, False]], "hop": 10, "slow": None,
     "brief": "Eight services, and three of them are optional extras with weak availability. They sit in the critical path unless you design around them.", "goal": "Do not let the weakest optional service decide your reliability."},
    {"name": "One slow service", "title": "A service with a long tail", "seed": 3, "services": [["gateway", 99.95, True], ["cart", 99.9, True], ["search", 99.5, False], ["pricing", 99.9, True], ["payments", 99.9, True]], "hop": 12, "slow": "search",
     "brief": "The search service is usually fast but sometimes takes seconds. Without a timeout it drags every checkout down with it.", "goal": "Keep both reliability and speed."},
]


def controls(level: int) -> List[Dict[str, Any]]:
    return [tog("fallback", "Fallbacks for optional services", False, "If an optional service fails, show the page without it."),
            tog("async", "Move optional work to events", False, "Optional services are triggered by events after checkout, instead of being called in the request."),
            tog("monolith_core", "Merge the essential services into one", False, "Fewer network hops and fewer things that can fail separately."),
            rng("timeout", "Timeout per call", 50, 2000, 50, 2000, "A call slower than this counts as failed.", " ms")]


def public_env(level: int) -> Dict[str, Any]:
    e = LEVELS[level]
    return {"services": [{"name": x[0], "avail": x[1], "essential": x[2]} for x in e["services"]], "reqs": REQS, "slow": e["slow"]}


def run(env: Dict[str, Any], s: Dict[str, Any]) -> Dict[str, Any]:
    rg = mulberry32(env["seed"])
    svcs = env["services"]
    essential = [x for x in svcs if x[2]]
    optional = [x for x in svcs if not x[2]]
    path: List[List[Any]] = []
    if s["monolith_core"]:
        a = 1.0
        for x in essential:
            a *= x[1] / 100.0
        path.append(["core (merged)", 100 * (1 - (1 - a) * 0.4), True])        # one process, so far fewer separate failure modes
    else:
        path.extend([list(x) for x in essential])
    if not s["async"]:
        path.extend([list(x) for x in optional])
    ok = degraded = failed = 0
    lat: List[float] = []
    fails = {x[0]: 0 for x in path}
    sample: List[Dict[str, Any]] = []
    for i in range(REQS):
        t = 0.0
        broke = None
        degraded_here = False
        for name, avail, ess in path:
            hop = env["hop"] * (0.6 if (s["monolith_core"] and name.startswith("core")) else 1.0)
            call = hop + 20 + rg() * 20
            if env["slow"] == name and rg() < 0.05:
                call += 3000
            fail = rg() > avail / 100.0 or call > s["timeout"]
            t += min(call, s["timeout"])
            if fail:
                if not ess and s["fallback"]:
                    degraded_here = True
                    continue
                fails[name] += 1
                broke = name
                break
        if broke:
            failed += 1
        elif degraded_here:
            degraded += 1
        else:
            ok += 1
        lat.append(t)
        if i < 60:
            sample.append({"i": i, "broke": broke, "degraded": degraded_here})
    lat.sort()
    month_minutes = 43200 * (failed / REQS)
    stats = {"success": round(100 * (ok + degraded) / REQS, 2), "degraded": degraded, "failed": failed, "p95": round(lat[int(0.95 * (REQS - 1))]), "path": [x[0] for x in path], "downtime": round(month_minutes, 1), "fails": fails}
    return {"frames": sample, "stats": stats, "insights": insights(env, s, stats)}


def insights(env: Dict[str, Any], s: Dict[str, Any], st: Dict[str, Any]) -> List[str]:
    out = [f"{st['success']}% of checkouts worked, which is about {st['downtime']} minutes of failure a month. The slowest 5% took {st['p95']} ms."]
    worst = max(st["fails"].items(), key=lambda kv: kv[1])
    if worst[1]:
        out.append(f"{worst[0]} caused the most failures ({worst[1]}).")
    if not s["fallback"] and any(not x[2] for x in env["services"]):
        out.append("Optional services are in the critical path, so their failures break checkout. A fallback lets checkout carry on without them.")
    if not s["async"] and len(st["path"]) > 5:
        out.append("The more services in a chain, the lower the combined availability. Moving optional work to events takes it off the critical path.")
    if env["slow"] and s["timeout"] > 1000:
        out.append("The slow service is dragging requests out to seconds. A short timeout plus a fallback keeps checkout fast.")
    if s["monolith_core"]:
        out.append("Merging the essential services removes network hops, which removes failure modes and latency.")
    return out


def badness(st: Dict[str, Any], env: Dict[str, Any]) -> float:
    return st["downtime"] / 5.0 + st["p95"] / 100.0 + st["degraded"] / 400.0
