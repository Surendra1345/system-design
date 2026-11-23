"""Streaming lab: a Kafka-style topic. Partitions cap parallelism, keys decide ordering and skew, and a slow consumer builds lag."""
from __future__ import annotations

from typing import Any, Dict, List

from .common import mulberry32, rng, sel

KIND = "streaming"
TICKS = 60
LEVELS: List[Dict[str, Any]] = [
    {"name": "Steady traffic", "title": "300 events a second", "rate": 300, "cap": 50, "hot": 0.0, "crash": None, "spike": None,
     "brief": "Events arrive at 300 a second and each consumer can handle 50 a second. Choose how many partitions and consumers to run.", "goal": "Keep the lag from growing."},
    {"name": "One huge customer", "title": "A hot key", "rate": 300, "cap": 50, "hot": 0.4, "crash": None, "spike": None,
     "brief": "Forty percent of the events belong to one huge customer. Whatever you choose as the key decides which partition gets them.", "goal": "Keep the lag low without losing the ordering of one customer's events."},
    {"name": "A consumer crashes", "title": "A rebalance in the middle of a spike", "rate": 300, "cap": 50, "hot": 0.0, "crash": 25, "spike": [30, 45, 1.6],
     "brief": "Traffic jumps by 60% and one consumer crashes at tick 25. The group pauses to rebalance, and the survivors must absorb its partitions.", "goal": "Recover from the crash without the lag exploding."},
]


def controls(level: int) -> List[Dict[str, Any]]:
    return [rng("partitions", "Partitions", 1, 12, 1, 2, "Each partition is read by at most one consumer in the group."),
            rng("consumers", "Consumers", 1, 12, 1, 2, "Consumers in the group. Extra consumers beyond the partition count sit idle."),
            sel("key", "Message key", [["user", "User ID (spreads evenly, keeps one user in order)"], ["customer", "Customer ID (skewed, keeps one customer in order)"], ["none", "No key (spreads evenly, no ordering)"]], "none", "The key decides the partition."),
            rng("spare", "Capacity headroom", 1.0, 2.0, 0.1, 1.0, "Run consumers on bigger machines: multiplies each consumer's speed.", "x")]


def public_env(level: int) -> Dict[str, Any]:
    e = LEVELS[level]
    return {"ticks": TICKS, "rate": e["rate"], "cap": e["cap"], "hot": e["hot"], "crash": e["crash"]}


def run(env: Dict[str, Any], s: Dict[str, Any]) -> Dict[str, Any]:
    rg = mulberry32(7)
    P, C = s["partitions"], s["consumers"]
    shares = [0.0] * P
    if s["key"] == "customer" and env["hot"] > 0:
        shares[0] += env["hot"]
        rest = 1.0 - env["hot"]
    else:
        rest = 1.0
    for i in range(P):
        shares[i] += rest / P
    lag = [0.0] * P
    pause = 0
    alive = C
    frames: List[Dict[str, Any]] = []
    ordering_broken = s["key"] == "none"
    for t in range(TICKS):
        rate = env["rate"]
        if env["spike"] and env["spike"][0] <= t < env["spike"][1]:
            rate *= env["spike"][2]
        if env["crash"] == t and alive > 1:
            alive -= 1
            pause = 4
        assign = [i % max(1, alive) for i in range(P)] if alive else []
        speed = env["cap"] * s["spare"]
        done = [0.0] * P
        if pause > 0:
            pause -= 1
        else:
            cons_load: Dict[int, List[int]] = {}
            for p, c in enumerate(assign):
                cons_load.setdefault(c, []).append(p)
            for c, parts in cons_load.items():
                budget = speed
                for p in sorted(parts, key=lambda x: -lag[x]):
                    take = min(budget, lag[p] + rate * shares[p])
                    done[p] = take
                    budget -= take
        for p in range(P):
            lag[p] = max(0.0, lag[p] + rate * shares[p] - done[p])
        frames.append({"t": t, "lag": [round(x) for x in lag], "alive": alive, "paused": pause > 0, "assign": assign, "total": round(sum(lag))})
    idle = max(0, alive - P)
    stats = {"max_lag": max(f["total"] for f in frames), "final_lag": frames[-1]["total"], "idle_consumers": idle, "ordering_broken": ordering_broken, "partitions": P, "consumers": C,
             "hot_partition": max(shares) > 1.5 / P if P > 1 else False}
    return {"frames": frames, "stats": stats, "insights": insights(env, s, stats)}


def insights(env: Dict[str, Any], s: Dict[str, Any], st: Dict[str, Any]) -> List[str]:
    out = [f"The backlog (lag) peaked at {st['max_lag']:,} events and ended at {st['final_lag']:,}."]
    if st["final_lag"] > 2000:
        out.append("Consumers could not keep up, so the lag kept growing. More consumers only help if there are partitions for them to read.")
    if st["idle_consumers"]:
        out.append(f"{st['idle_consumers']} consumers sat idle. A partition is read by one consumer in a group, so parallelism is capped by the number of partitions.")
    if st["hot_partition"] and s["key"] == "customer":
        out.append("One customer produces most of the events, and all of them land on one partition, so a single consumer drowns while the others are idle. Pick a key that spreads load.")
    if st["ordering_broken"]:
        out.append("With no key, events from one user can land on different partitions and be processed out of order.")
    if env["crash"] is not None:
        out.append("When a consumer dies the group pauses to rebalance, and its partitions move to the others. Spare capacity absorbs that.")
    return out


def badness(st: Dict[str, Any], env: Dict[str, Any]) -> float:
    return st["max_lag"] / 200.0 + st["final_lag"] / 100.0 + (25 if st["ordering_broken"] else 0) + 3 * st["idle_consumers"] + 1.0 * st["consumers"] * 0.2
