"""Replication lab: a primary and followers. Followers share the reads but lag behind, and a crash can lose writes that were not copied yet."""
from __future__ import annotations

from typing import Any, Dict, List

from .common import mulberry32, rng, sel

KIND = "repl"
KEYS = 100
LEVELS: List[Dict[str, Any]] = [
    {"name": "Too many reads", "title": "One database cannot answer every read", "seed": 2, "ticks": 60, "writes": 4, "reads": 20, "cap": 14, "lags": [2, 6, 3], "ryw": 0.0, "crash": None,
     "brief": "Your primary database can do 14 operations a tick but gets 4 writes and 20 reads. Followers hold copies and can answer reads, but each copy arrives a little late.", "goal": "Serve every read without showing out-of-date data."},
    {"name": "Just saved", "title": "Users reload right after saving", "seed": 4, "ticks": 60, "writes": 4, "reads": 20, "cap": 14, "lags": [2, 6, 3], "ryw": 0.3, "crash": None,
     "brief": "30% of reads are people looking at something they saved a moment ago. If that read lands on a follower that has not received the copy yet, their change seems to have vanished.", "goal": "Keep the load off the primary and never lose someone's own change."},
    {"name": "Primary dies", "title": "The primary crashes at tick 30", "seed": 6, "ticks": 60, "writes": 4, "reads": 20, "cap": 14, "lags": [2, 6, 3], "ryw": 0.3, "crash": 30,
     "brief": "At tick 30 the primary crashes and the freshest follower takes over after 3 ticks. Writes that the old primary had not yet copied are gone for good.", "goal": "Survive the crash without losing writes that users were told succeeded."},
]


def controls(level: int) -> List[Dict[str, Any]]:
    return [rng("followers", "Followers", 0, 3, 1, 0, "Copies of the database that can answer reads. Each one costs money."),
            sel("read_from", "Where reads go", [["leader", "Always the primary"], ["followers", "Followers only"], ["smart", "Followers, but your own recent writes from the primary"]], "leader", "Read routing."),
            sel("ack", "When is a write a success?", [["async", "As soon as the primary has it (async)"], ["semi", "When one follower also has it (semi-sync)"], ["sync", "When every follower has it (sync)"]], "async", "Waiting for followers makes a write slower but safer.")]


def public_env(level: int) -> Dict[str, Any]:
    e = LEVELS[level]
    return {"ticks": e["ticks"], "cap": e["cap"], "lags": e["lags"], "crash": e["crash"], "writes": e["writes"], "reads": e["reads"]}


def run(env: Dict[str, Any], s: Dict[str, Any]) -> Dict[str, Any]:
    rg = mulberry32(env["seed"])
    n = s["followers"]
    lags = env["lags"][:n]
    writes: List[Any] = []                                 # (tick, key)
    last_write: Dict[int, int] = {}
    stale = served = unserved = failed_w = lost = 0
    wlat_sum, wcount = 0.0, 0
    rr = 0
    frames: List[Dict[str, Any]] = []
    crash = env["crash"]
    promoted = min(range(n), key=lambda i: lags[i]) if n else None
    for t in range(env["ticks"]):
        down = crash is not None and crash <= t < crash + 3
        after = crash is not None and t >= crash + 3
        if crash is not None and t == crash:
            if n == 0:
                lost += len(writes)
            elif s["ack"] == "async":
                lost += sum(1 for w in writes if w[0] > crash - lags[promoted])
        if after:                                           # the promoted follower is now the primary
            lags_now = [l for i, l in enumerate(lags) if i != promoted]
        else:
            lags_now = lags
        wtick = []
        for _ in range(env["writes"]):
            if down:
                failed_w += 1
                continue
            k = int(rg() * KEYS)
            writes.append((t, k))
            last_write[k] = t
            wtick.append(k)
            wcount += 1
            lat = 5.0
            if lags_now and s["ack"] == "semi":
                lat += 10 * min(lags_now)
            elif lags_now and s["ack"] == "sync":
                lat += 10 * max(lags_now)
            wlat_sum += lat
        recent = [k for (tw, k) in writes if t - tw <= 4]
        load = len(wtick)
        sample = []
        for r in range(env["reads"]):
            own = r < int(env["reads"] * env["ryw"]) and recent
            key = recent[int(rg() * len(recent))] if own else int(rg() * KEYS)
            if down:
                unserved += 1
                continue
            to = "L"
            if s["read_from"] == "followers" and lags_now:
                to = rr % len(lags_now); rr += 1
            elif s["read_from"] == "smart" and lags_now and not own:
                to = rr % len(lags_now); rr += 1
            if to == "L":
                if load >= env["cap"]:
                    unserved += 1
                    continue
                load += 1
                served += 1
                if len(sample) < 10:
                    sample.append(["L", 0])
            else:
                served += 1
                is_stale = key in last_write and last_write[key] + lags_now[to] > t and last_write[key] <= t and last_write[key] != t
                if is_stale:
                    stale += 1
                if len(sample) < 10:
                    sample.append([to, 1 if is_stale else 0])
        pending = [sum(1 for (tw, _) in writes if tw + l > t) for l in lags_now]
        frames.append({"t": t, "writes": len(wtick), "pending": pending, "reads": sample, "load": load, "down": down, "after": after, "lost": lost, "stale": stale, "unserved": unserved})
    total_reads = max(1, served + unserved)
    stats = {"stale_frac": round(stale / max(1, served), 3), "unserved_frac": round(unserved / total_reads, 3), "write_ms": round(wlat_sum / max(1, wcount), 1), "lost": lost,
             "failed_writes": failed_w, "followers": n, "cap": env["cap"]}
    return {"frames": frames, "stats": stats, "insights": insights(env, s, stats)}


def insights(env: Dict[str, Any], s: Dict[str, Any], st: Dict[str, Any]) -> List[str]:
    out = [f"{st['unserved_frac'] * 100:.0f}% of reads could not be answered and {st['stale_frac'] * 100:.0f}% of answers were out of date. A write took {st['write_ms']:.0f} ms on average."]
    if st["unserved_frac"] > 0.05 and s["read_from"] == "leader":
        out.append("Every read goes to the primary, which is already busy with writes, so it drops requests. Followers can share the reads.")
    if st["stale_frac"] > 0.03:
        out.append("Followers receive each write a few ticks after the primary, so a read there can return old data (replication lag).")
        if s["read_from"] == "followers" and env["ryw"] > 0:
            out.append("Someone who just saved a change and reloads may land on a follower that does not have it yet. Send their own recent writes to the primary (read-your-writes).")
    if env["crash"] is not None and st["lost"] > 0:
        out.append(f"{st['lost']} writes that users were told had succeeded were lost in the crash, because the primary had not copied them yet. Waiting for a follower to confirm (semi-sync) prevents it.")
    if s["ack"] == "sync" and st["write_ms"] > 50:
        out.append("Waiting for every follower makes writes as slow as the slowest copy.")
    return out


def badness(st: Dict[str, Any], env: Dict[str, Any]) -> float:
    return 100 * st["stale_frac"] + 100 * st["unserved_frac"] + st["write_ms"] / 10 + 8 * st["lost"] + 2 * st["failed_writes"] + 1.5 * st["followers"]
