"""Rate limiter lab: let real users through, stop abuse. Three algorithms behave very differently on bursts."""
from __future__ import annotations

from typing import Any, Dict, List

from .common import mulberry32, rng, sel

KIND = "limiter"
LEVELS: List[Dict[str, Any]] = [
    {"name": "A bot", "title": "One client floods the API", "seed": 2, "ticks": 60, "clients": [{"n": 12, "kind": "legit", "rate": 1.0, "burst": 0, "shared": False}, {"n": 1, "kind": "abuse", "rate": 18, "burst": 0, "shared": False}],
     "brief": "Twelve normal users make about one request per tick. One bot makes eighteen. Allow the users and stop the bot.", "goal": "Block the bot without blocking real users."},
    {"name": "Burst traffic", "title": "Real users click in bursts", "seed": 6, "ticks": 60, "clients": [{"n": 12, "kind": "legit", "rate": 1.0, "burst": 8, "shared": False}, {"n": 1, "kind": "abuse", "rate": 0, "burst": 45, "shared": False, "pulse": 10, "pulse_ticks": [4, 5]}],
     "brief": "Real users sometimes click eight times at once, then go quiet. The abuser sends 45 requests in the last tick of a window and 45 more in the first tick of the next one, so a fixed window counts them as two separate bursts.", "goal": "Allow short bursts but stop the sustained flood."},
    {"name": "Shared address", "title": "An office behind one IP address", "seed": 10, "ticks": 60, "clients": [{"n": 10, "kind": "legit", "rate": 1.2, "burst": 4, "shared": True}, {"n": 6, "kind": "legit", "rate": 1.0, "burst": 0, "shared": False}, {"n": 1, "kind": "abuse", "rate": 16, "burst": 0, "shared": False}],
     "brief": "Ten employees share one office IP address. If you count requests per IP, they use up one allowance together.", "goal": "Do not lock out the whole office because of its shared IP."},
]


def controls(level: int) -> List[Dict[str, Any]]:
    return [sel("algo", "Algorithm", [["fixed", "Fixed window counter"], ["sliding", "Sliding window log"], ["bucket", "Token bucket"]], "fixed", "How requests are counted."),
            rng("limit", "Requests allowed per window", 1, 40, 1, 5, "Used by the two window algorithms."),
            rng("window", "Window length", 1, 10, 1, 1, "Used by the two window algorithms.", " ticks"),
            rng("bucket", "Bucket size", 1, 40, 1, 5, "Token bucket: the biggest burst allowed."),
            rng("refill", "Refill per tick", 0.5, 10, 0.5, 1, "Token bucket: tokens added every tick, the steady rate allowed."),
            sel("key", "Count requests per", [["ip", "IP address"], ["user", "User account"]], "ip", "Who the limit applies to.")]


def public_env(level: int) -> Dict[str, Any]:
    e = LEVELS[level]
    return {"ticks": e["ticks"], "groups": [{"kind": c["kind"], "n": c["n"], "shared": c["shared"]} for c in e["clients"]]}


def run(env: Dict[str, Any], s: Dict[str, Any]) -> Dict[str, Any]:
    rg = mulberry32(env["seed"])
    clients: List[Dict[str, Any]] = []
    uid = 0
    for g in env["clients"]:
        for _ in range(g["n"]):
            clients.append({"user": uid, "ip": 0 if g["shared"] else 1000 + uid, "g": g})
            uid += 1
    state: Dict[Any, Any] = {}
    tot = {"legit": [0, 0], "abuse": [0, 0]}
    frames: List[Dict[str, Any]] = []

    def allow(key: Any, t: int) -> bool:
        st = state.setdefault(key, {"win": -1, "cnt": 0, "log": [], "tok": float(s["bucket"]), "last": t})
        if s["algo"] == "fixed":
            w = t // s["window"]
            if st["win"] != w:
                st["win"], st["cnt"] = w, 0
            if st["cnt"] < s["limit"]:
                st["cnt"] += 1
                return True
            return False
        if s["algo"] == "sliding":
            st["log"] = [x for x in st["log"] if x > t - s["window"]]
            if len(st["log"]) < s["limit"]:
                st["log"].append(t)
                return True
            return False
        st["tok"] = min(float(s["bucket"]), st["tok"] + s["refill"] * (t - st["last"]))
        st["last"] = t
        if st["tok"] >= 1:
            st["tok"] -= 1
            return True
        return False

    for t in range(env["ticks"]):
        row = {"legit": [0, 0], "abuse": [0, 0]}
        for c in clients:
            g = c["g"]
            n = 0
            if g.get("pulse"):
                n = g["burst"] if t % g["pulse"] in g["pulse_ticks"] else 0
            else:
                n = int(g["rate"]) + (1 if rg() < g["rate"] - int(g["rate"]) else 0)
                if g["burst"] and rg() < 0.07:
                    n += g["burst"]
            key = c["ip"] if s["key"] == "ip" else c["user"]
            for _ in range(n):
                ok = allow(key, t)
                row[g["kind"]][0 if ok else 1] += 1
                tot[g["kind"]][0 if ok else 1] += 1
        tokens = None
        if s["algo"] == "bucket":
            tokens = round(min(state[k]["tok"] for k in state), 1) if state else s["bucket"]
        frames.append({"t": t, "legit": row["legit"], "abuse": row["abuse"], "tokens": tokens})
    la, lb = tot["legit"]
    aa, ab = tot["abuse"]
    stats = {"legit_blocked": round(lb / max(1, la + lb), 3), "abuse_allowed": round(aa / max(1, aa + ab), 3), "legit_total": la + lb, "abuse_total": aa + ab,
             "abuse_passed": aa, "legit_blocked_n": lb}
    return {"frames": frames, "stats": stats, "insights": insights(env, s, stats)}


def insights(env: Dict[str, Any], s: Dict[str, Any], st: Dict[str, Any]) -> List[str]:
    out = [f"{st['legit_blocked'] * 100:.0f}% of real requests were blocked, and {st['abuse_allowed'] * 100:.0f}% of the abusive requests got through."]
    if st["legit_blocked"] > 0.05:
        out.append("Real users are being turned away. Allow bigger bursts, or count them separately.")
    if st["abuse_allowed"] > 0.25:
        out.append("Too much abuse gets through. Lower the sustained rate that is allowed.")
    if s["algo"] == "fixed" and st["abuse_allowed"] > 0.25:
        out.append("A fixed window resets all at once, so a client can send a full allowance at the end of one window and another at the start of the next.")
    if s["algo"] == "bucket":
        out.append("A token bucket allows a short burst up to the bucket size, then limits the client to the refill rate.")
    if s["key"] == "ip" and any(g["shared"] for g in env["clients"]) and st["legit_blocked"] > 0.05:
        out.append("Many people share one IP address (offices, schools, mobile networks), so counting per IP punishes all of them. Count per user account.")
    return out


def badness(st: Dict[str, Any], env: Dict[str, Any]) -> float:
    return 100 * st["legit_blocked"] + 100 * st["abuse_allowed"]
