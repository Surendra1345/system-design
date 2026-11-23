"""Clocks lab: servers disagree about the time. Last-write-wins on timestamps can throw away the newest write."""
from __future__ import annotations

from typing import Any, Dict, List

from .common import mulberry32, rng, sel

KIND = "clocks"
EPS = 7.0                       # TrueTime-style uncertainty in ms; a write waits 2 * EPS before it is acknowledged
LEVELS: List[Dict[str, Any]] = [
    {"name": "Causal chain", "title": "Each edit follows the last one", "seed": 3, "n": 40, "gap": [50, 250], "causal": True, "off": [0, 80, -120], "drift": [0, 5, -4], "needs_time": False,
     "brief": "Three servers hold copies of a document. Each edit is made after the user saw the previous edit, but through a different server. The copy with the larger timestamp wins, and the servers' clocks are off by up to 120 ms.", "goal": "Never let an older edit overwrite a newer one."},
    {"name": "Drifting clocks", "title": "Cheap clocks drift apart over time", "seed": 5, "n": 120, "gap": [300, 700], "causal": True, "off": [0, 10, -10], "drift": [0, 28, -24], "needs_time": True,
     "brief": "Over a minute the clocks drift by tens of milliseconds a second. An audit trail also needs timestamps that look like real time, so a bare counter is not good enough.", "goal": "Keep edits in order and keep timestamps close to real time."},
    {"name": "Strangers", "title": "Two people who never talk, 20 ms apart", "seed": 7, "n": 120, "gap": [10, 40], "causal": False, "off": [0, 30, -40], "drift": [0, 6, -5], "needs_time": False,
     "brief": "Different users write through different servers without any message between them, a few milliseconds after each other. Real-time order must still hold: if one write finished before another began, it must be ordered first.", "goal": "Order writes by real time, even with unsynchronised clocks."},
]


def controls(level: int) -> List[Dict[str, Any]]:
    return [sel("stamp", "How a write gets its timestamp", [["wall", "The server's own clock"], ["lamport", "A logical counter (Lamport)"], ["hlc", "Hybrid logical clock"], ["truetime", "Atomic clock with wait (TrueTime)"]], "wall", "The number used to decide which write is newest."),
            rng("ntp", "Sync clocks every", 0, 60, 1, 0, "Seconds between time-server syncs. 0 means never.", " s")]


def public_env(level: int) -> Dict[str, Any]:
    e = LEVELS[level]
    return {"n": e["n"], "off": e["off"], "drift": e["drift"], "causal": e["causal"], "needs_time": e["needs_time"]}


def run(env: Dict[str, Any], s: Dict[str, Any]) -> Dict[str, Any]:
    rg = mulberry32(env["seed"])
    counters = [0, 0, 0]
    t = 0.0
    prev_ts, prev_srv, client_ts = None, None, 0.0
    viol = 0
    frames: List[Dict[str, Any]] = []
    ts_err: List[float] = []
    latency = 2 * EPS if s["stamp"] == "truetime" else 1.0
    for k in range(env["n"]):
        t += env["gap"][0] + rg() * (env["gap"][1] - env["gap"][0])
        srv = int(rg() * 3)
        if prev_srv is not None and srv == prev_srv:
            srv = (srv + 1) % 3
        sec = t / 1000.0
        since = sec if s["ntp"] == 0 else sec % s["ntp"]
        off = env["off"][srv] * (1.0 if s["ntp"] == 0 else 0.1) + env["drift"][srv] * since
        if s["stamp"] == "truetime":
            off = (rg() - 0.5) * 4
        phys = t + off
        if s["stamp"] == "wall":
            ts = phys
        elif s["stamp"] == "lamport":
            ts = max(counters[srv], client_ts if env["causal"] else 0) + 1
            counters[srv] = ts
        elif s["stamp"] == "hlc":
            ts = max(phys, (client_ts + 0.001) if env["causal"] else 0)
        else:
            ts = phys + EPS
            t += 2 * EPS                       # commit wait
        bad = prev_ts is not None and ts <= prev_ts
        viol += 1 if bad else 0
        if s["stamp"] != "lamport":
            ts_err.append(abs(ts - t))
        frames.append({"t": k, "ms": round(t), "srv": srv, "ts": round(ts, 1), "off": round(off, 1), "bad": bool(bad)})
        prev_ts, prev_srv, client_ts = ts, srv, ts
    stats = {"violations": viol, "viol_frac": round(viol / max(1, env["n"] - 1), 3), "latency": round(latency, 1), "time_err": round(sum(ts_err) / max(1, len(ts_err)), 1),
             "needs_time_fail": bool(env["needs_time"] and s["stamp"] == "lamport")}
    return {"frames": frames, "stats": stats, "insights": insights(env, s, stats)}


def insights(env: Dict[str, Any], s: Dict[str, Any], st: Dict[str, Any]) -> List[str]:
    out = [f"{st['violations']} of {env['n'] - 1} edits were ordered wrongly, so a newer edit lost to an older one. Each write took about {st['latency']:.0f} ms."]
    if s["stamp"] == "wall" and st["violations"]:
        out.append("The server that handled the newer edit had a clock running behind, so it stamped the newer edit with an older time. Wall clocks cannot be trusted to order events.")
    if s["stamp"] == "lamport" and not env["causal"] and st["violations"]:
        out.append("A logical counter only orders events that are connected by messages. Two users who never talk can be ordered the wrong way round.")
    if st["needs_time_fail"]:
        out.append("A logical counter is correct for ordering, but it says nothing about when something happened. A hybrid logical clock keeps both.")
    if s["stamp"] == "truetime":
        out.append("Waiting out the clock uncertainty makes real-time order safe, and it costs 14 ms on every write. That is the price of needing atomic clocks.")
    if s["stamp"] == "wall" and s["ntp"] == 0 and env["drift"][1] != 5:
        out.append("The clocks were never synced, so the drift keeps growing. Syncing more often keeps the error small.")
    return out


def badness(st: Dict[str, Any], env: Dict[str, Any]) -> float:
    return 100 * st["viol_frac"] + st["latency"] / 2 + (30 if st["needs_time_fail"] else 0) + (st["time_err"] / 200 if env["needs_time"] else 0)
