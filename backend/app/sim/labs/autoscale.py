"""Autoscaling lab: follow a load curve with capacity. Too slow and users are dropped, too eager and you pay for idle servers."""
from __future__ import annotations

import math
from typing import Any, Dict, List

from .common import mulberry32, rng, tog

KIND = "autoscale"
PER = 10.0          # requests one instance handles per tick
START = 4           # ticks for a new instance to boot
TICKS = 100
LEVELS: List[Dict[str, Any]] = [
    {"name": "Daily wave", "title": "Traffic rises and falls through the day", "seed": 3, "shape": "wave", "max_cap": 20,
     "brief": "Traffic climbs through the morning and falls at night. A new instance takes 4 ticks to boot, and every running instance costs money.", "goal": "Serve everyone without paying for idle servers."},
    {"name": "Flash sale", "title": "Traffic jumps five times in seconds", "seed": 5, "shape": "spike", "max_cap": 20,
     "brief": "At tick 30 a sale starts and traffic jumps to five times normal for 20 ticks. Instances that are still booting cannot help yet.", "goal": "Survive the jump and shrink again afterwards."},
    {"name": "Choppy load", "title": "Traffic bounces up and down", "seed": 8, "shape": "choppy", "max_cap": 20,
     "brief": "Traffic keeps jumping between busy and quiet. If you scale down the moment it is quiet, you have to scale up again with boot delays.", "goal": "Avoid flapping: do not remove servers you will need in a moment."},
]


def curve(env: Dict[str, Any]) -> List[float]:
    rg = mulberry32(env["seed"])
    out = []
    for t in range(TICKS):
        if env["shape"] == "wave":
            v = 60 + 55 * math.sin(2 * math.pi * (t - 20) / 100.0)
        elif env["shape"] == "spike":
            v = 40 + (160 if 30 <= t < 50 else 0)
        else:
            v = 50 + (70 if (t // 8) % 2 == 1 else 0)
        out.append(max(5.0, v * (1 + (rg() - 0.5) * 0.12)))
    return out


def controls(level: int) -> List[Dict[str, Any]]:
    return [rng("min", "Minimum instances", 1, 10, 1, 1, "Never go below this."),
            rng("max", "Maximum instances", 1, LEVELS[level]["max_cap"], 1, 4, "Never go above this. It also caps your bill."),
            rng("up_at", "Add instances above", 40, 95, 5, 90, "Utilisation that triggers scaling up.", "%"),
            rng("down_at", "Remove instances below", 10, 60, 5, 30, "Utilisation that triggers scaling down.", "%"),
            rng("cooldown", "Wait between changes", 0, 20, 1, 0, "Ticks to wait after a change before the next one.", " ticks"),
            rng("step", "Instances added at a time", 1, 5, 1, 1, "A bigger step reacts faster to a jump."),
            tog("warm", "Warm pool", False, "Keep pre-booted spare instances ready (boot in 1 tick, small extra cost).")]


def public_env(level: int) -> Dict[str, Any]:
    e = LEVELS[level]
    return {"ticks": TICKS, "per": PER, "start": START, "load": [round(x, 1) for x in curve(e)], "max_cap": e["max_cap"]}


def run(env: Dict[str, Any], s: Dict[str, Any]) -> Dict[str, Any]:
    load = curve(env)
    ready = s["min"]
    booting: List[int] = []                 # ticks left for each booting instance
    last_change = -999
    dropped = served = 0.0
    cost = 0.0
    frames: List[Dict[str, Any]] = []
    boot = 1 if s["warm"] else START
    changes = 0
    for t in range(TICKS):
        booting = [x - 1 for x in booting]
        ready += sum(1 for x in booting if x <= 0)
        booting = [x for x in booting if x > 0]
        cap = ready * PER
        util = load[t] / cap if cap else 9.0
        total = ready + len(booting)
        if t - last_change >= s["cooldown"]:
            if util * 100 > s["up_at"] and total < s["max"]:
                add = min(s["step"], s["max"] - total)
                booting += [boot] * add
                last_change = t
                changes += 1
            elif util * 100 < s["down_at"] and ready > s["min"] and not booting:
                ready -= 1
                last_change = t
                changes += 1
        sv = min(load[t], cap)
        served += sv
        dropped += load[t] - sv
        cost += ready + len(booting) + (1.0 * 0.4 if s["warm"] else 0.0)
        frames.append({"t": t, "load": round(load[t], 1), "cap": round(cap, 1), "ready": ready, "booting": len(booting), "dropped": round(load[t] - sv, 1)})
    base = (max(load) / PER) * TICKS
    drop_frac = dropped / max(1.0, served + dropped)
    stats = {"drop_frac": round(drop_frac, 3), "cost": round(cost), "baseline": round(base), "cost_frac": round(cost / base, 3), "changes": changes, "dropped": round(dropped)}
    return {"frames": frames, "stats": stats, "insights": insights(env, s, stats)}


def insights(env: Dict[str, Any], s: Dict[str, Any], st: Dict[str, Any]) -> List[str]:
    out = [f"{st['drop_frac'] * 100:.1f}% of requests were dropped. You paid {st['cost_frac'] * 100:.0f}% of what it would cost to run for the peak all the time."]
    if st["drop_frac"] > 0.05 and s["max"] < env["max_cap"]:
        out.append("Dropped requests mean capacity was short. Your maximum may be too low, or scaling starts too late.")
    if st["drop_frac"] > 0.05 and s["up_at"] > 75:
        out.append("You wait until servers are nearly full before adding more, and new instances take time to boot. Scaling up earlier gives you headroom.")
    if st["drop_frac"] > 0.05 and s["step"] == 1 and env["shape"] == "spike":
        out.append("When traffic jumps, adding one instance at a time is too slow. Add several at once.")
    if st["changes"] > 18 and s["cooldown"] < 3:
        out.append(f"You changed capacity {st['changes']} times. A short wait between changes stops the fleet from flapping.")
    if st["cost_frac"] > 0.7:
        out.append("Capacity stays high for a long time. Scale down sooner, or lower the maximum.")
    if s["warm"]:
        out.append("A warm pool shortens the boot delay at the price of paying for spare instances.")
    return out


def badness(st: Dict[str, Any], env: Dict[str, Any]) -> float:
    return 100 * st["drop_frac"] + 10 * st["cost_frac"]
