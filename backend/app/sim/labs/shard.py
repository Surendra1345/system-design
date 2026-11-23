"""Sharding lab: spread keys over shards. Hot keys, growing data and adding a shard show why the strategy matters."""
from __future__ import annotations

import bisect
import math
from typing import Any, Dict, List

from .common import mulberry32, rng, sel, tog

KIND = "shard"
N_KEYS = 1200
LEVELS: List[Dict[str, Any]] = [
    {"name": "Even spread", "title": "Spread a user table over shards", "seed": 4, "mode": "flat", "grow": False, "cap": 0.3, "max_shards": 8,
     "brief": "Your user table is too big for one database. Split it over shards. Every key is about equally popular.", "goal": "Keep every shard about equally busy."},
    {"name": "New is hot", "title": "The newest rows get all the traffic", "seed": 8, "mode": "recent", "grow": False, "cap": 0.2, "max_shards": 8,
     "brief": "Keys are numbered in the order they were created, and the newest ones are the most popular, like orders or posts. Some strategies pile all of that onto one shard.", "goal": "Spread the recent keys over all shards."},
    {"name": "Growing", "title": "Add a shard without moving everything", "seed": 12, "mode": "hotkeys", "grow": True, "cap": 0.2, "max_shards": 8,
     "brief": "A few celebrity keys are extremely popular. Next month you will add one more shard, and every key that moves must be copied across the network.", "goal": "Balance the load now and keep the move to a new shard small."},
]


def controls(level: int) -> List[Dict[str, Any]]:
    c = [rng("shards", "Number of shards", 2, LEVELS[level]["max_shards"], 1, 2, "More shards share the load, but cost more to run."),
         sel("strategy", "How keys pick a shard", [["mod", "Hash the key, then key mod N"], ["range", "Ranges of key numbers"], ["ring", "Consistent hashing ring"]], "mod", "The sharding strategy."),
         rng("vnodes", "Virtual nodes per shard", 1, 40, 1, 1, "Only used by the ring. More points per shard even out the ring.")]
    if LEVELS[level]["mode"] == "hotkeys":
        c.append(tog("split_hot", "Replicate the hottest keys", False, "Copy the hottest keys to every shard so reads spread out."))
    return c


def public_env(level: int) -> Dict[str, Any]:
    e = LEVELS[level]
    return {"keys": N_KEYS, "mode": e["mode"], "grow": e["grow"], "max_shards": e["max_shards"], "cap": e["cap"]}


def _h(x: int) -> int:
    x = (x ^ 61) ^ (x >> 16)
    x = (x + (x << 3)) & 0xFFFFFFFF
    x ^= x >> 4
    x = (x * 0x27D4EB2D) & 0xFFFFFFFF
    x ^= x >> 15
    return x & 0xFFFFFFFF


def _weights(env: Dict[str, Any]) -> List[float]:
    if env["mode"] == "flat":
        return [1.0] * N_KEYS
    if env["mode"] == "recent":
        return [math.exp(4.0 * k / N_KEYS) for k in range(N_KEYS)]
    w = [1.0] * N_KEYS
    for k in (17, 403, 777):
        w[k] = 90.0
    return w


def _assign(strategy: str, n: int, vnodes: int) -> List[int]:
    if strategy == "mod":
        return [_h(k) % n for k in range(N_KEYS)]
    if strategy == "range":
        return [min(n - 1, k * n // N_KEYS) for k in range(N_KEYS)]
    ring = sorted((_h(s * 100003 + v * 7919 + 13), s) for s in range(n) for v in range(vnodes))
    pts = [p for p, _ in ring]
    out = []
    for k in range(N_KEYS):
        i = bisect.bisect_left(pts, _h(k * 2654435761 % 4294967296 + 5)) % len(ring)
        out.append(ring[i][1])
    return out


def _loads(env: Dict[str, Any], s: Dict[str, Any], n: int) -> List[float]:
    w = _weights(env)
    a = _assign(s["strategy"], n, s["vnodes"])
    hot = set(sorted(range(N_KEYS), key=lambda k: -w[k])[:3]) if (env["mode"] == "hotkeys" and s.get("split_hot")) else set()
    loads = [0.0] * n
    for k in range(N_KEYS):
        if k in hot:
            for i in range(n):
                loads[i] += w[k] / n
        else:
            loads[a[k]] += w[k]
    return loads


def run(env: Dict[str, Any], s: Dict[str, Any]) -> Dict[str, Any]:
    n = s["shards"]
    loads = _loads(env, s, n)
    avg = sum(loads) / n
    imbalance = max(loads) / avg - 1.0
    moved = 0.0
    if env["grow"]:
        a1, a2 = _assign(s["strategy"], n, s["vnodes"]), _assign(s["strategy"], n + 1, s["vnodes"])
        moved = sum(1 for k in range(N_KEYS) if a1[k] != a2[k]) / N_KEYS
    rg = mulberry32(env["seed"])
    w = _weights(env)
    tot = sum(w)
    cdf, acc = [], 0.0
    for x in w:
        acc += x / tot
        cdf.append(acc)
    a = _assign(s["strategy"], n, s["vnodes"])
    counts = [0] * n
    frames: List[Dict[str, Any]] = []
    for i in range(300):
        u = rg()
        k = bisect.bisect_left(cdf, u)
        k = min(k, N_KEYS - 1)
        counts[a[k]] += 1
        if i % 15 == 14:
            frames.append({"t": len(frames), "counts": list(counts), "last_key": k})
    ring = []
    if s["strategy"] == "ring":
        ring = [[round(_h(sh * 100003 + v * 7919 + 13) / 4294967296, 4), sh] for sh in range(n) for v in range(min(s["vnodes"], 12))]
    shares = [x / sum(loads) for x in loads]
    overload = max(0.0, (max(shares) - env["cap"]) / env["cap"])
    stats = {"loads": [round(x, 3) for x in shares], "imbalance": round(imbalance, 3), "moved": round(moved, 3), "ring": ring, "shards": n, "overload": round(overload, 3), "cap": env["cap"]}
    return {"frames": frames, "stats": stats, "insights": insights(env, s, stats)}


def insights(env: Dict[str, Any], s: Dict[str, Any], st: Dict[str, Any]) -> List[str]:
    hi = max(st["loads"]) * 100
    out = [f"The busiest shard takes {hi:.0f}% of the traffic. A perfect split would be {100 / st['shards']:.0f}% each, and one shard can safely handle {env['cap'] * 100:.0f}%."]
    if st["overload"] > 0:
        out.append("At least one shard is over its capacity. Add shards, or spread the traffic more evenly.")
    if s["strategy"] == "range" and env["mode"] == "recent":
        out.append("With ranges, all the newest keys sit in the last range, so one shard does most of the work. Hashing scatters neighbouring keys.")
    if s["strategy"] == "ring" and s["vnodes"] < 8:
        out.append("A ring with only a few points per shard leaves uneven gaps. More virtual nodes even them out.")
    if env["grow"]:
        out.append(f"Adding a shard would move {st['moved'] * 100:.0f}% of all keys.")
        if s["strategy"] == "mod" and st["moved"] > 0.4:
            out.append("With key mod N, changing N changes the home of almost every key. A consistent hashing ring only moves the keys the new shard takes over.")
    if env["mode"] == "hotkeys" and not s.get("split_hot") and st["imbalance"] > 0.5:
        out.append("A few keys are so popular that whichever shard owns them is overloaded. Hashing cannot split one key. Replicate the hottest keys.")
    return out


def badness(st: Dict[str, Any], env: Dict[str, Any]) -> float:
    return st["overload"] * 300 + st["imbalance"] * 100 + st["moved"] * 100 + 2 * st["shards"]
