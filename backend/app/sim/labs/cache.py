"""Caching lab: a stream of requests, a small cache, and a database that cannot keep up with too many misses."""
from __future__ import annotations

import math
from collections import OrderedDict
from typing import Any, Dict, List

from .common import mulberry32, rng, sel, tog

KIND = "cache"
LEVELS: List[Dict[str, Any]] = [
    {"name": "Popular keys", "title": "A catalogue with a few popular items", "seed": 5, "fresh": 40, "keys": 300, "zipf": 1.1, "rate": 14, "ticks": 80, "db_cap": 6, "hit_ms": 2, "miss_ms": 60, "max_slots": 40, "shift_at": None,
     "brief": "Most requests ask for a few popular items, but there are 300 items in total. Memory is limited, and every miss goes to a slow database.", "goal": "Keep the average response fast without overloading the database."},
    {"name": "Trends change", "title": "The popular items change halfway through", "seed": 9, "fresh": 40, "keys": 300, "zipf": 1.1, "rate": 14, "ticks": 80, "db_cap": 6, "hit_ms": 2, "miss_ms": 60, "max_slots": 40, "shift_at": 40,
     "brief": "At tick 40 a different set of items becomes popular, like a news story breaking. Your eviction policy decides how fast the cache adapts.", "goal": "Stay fast before and after the trend changes."},
    {"name": "Expiry waves", "title": "Everything expires at the same moment", "seed": 13, "fresh": 40, "keys": 300, "zipf": 1.2, "rate": 18, "ticks": 80, "db_cap": 8, "hit_ms": 2, "miss_ms": 60, "max_slots": 60, "shift_at": None, "warm": True,
     "brief": "Entries expire after a time to live (TTL). The cache was filled in one go after a restart, so all of its entries expire at the same moment and the misses hit the database together.", "goal": "Avoid the database spikes while staying fast."},
]


def controls(level: int) -> List[Dict[str, Any]]:
    mx = LEVELS[level]["max_slots"]
    return [rng("size", "Cache size", 2, mx, 1, 4, "How many items fit in memory. Bigger is faster but costs more.", " slots"),
            sel("policy", "When full, throw out", [["fifo", "The oldest item (FIFO)"], ["lru", "The least recently used (LRU)"], ["lfu", "The least often used (LFU)"]], "fifo", "The eviction policy."),
            rng("ttl", "Time to live", 0, 60, 5, 0, "How long an item may stay before it expires. 0 means never.", " ticks"),
            tog("jitter", "Spread out expiry times", False, "Add a random amount to each TTL so items do not all expire together."),
            tog("coalesce", "Merge duplicate misses", False, "If many requests miss on the same item in the same moment, ask the database once.")]


def public_env(level: int) -> Dict[str, Any]:
    e = LEVELS[level]
    return {"keys": e["keys"], "ticks": e["ticks"], "fresh": e["fresh"], "db_cap": e["db_cap"], "shift_at": e["shift_at"], "hit_ms": e["hit_ms"], "miss_ms": e["miss_ms"]}


def run(env: Dict[str, Any], s: Dict[str, Any]) -> Dict[str, Any]:
    rg = mulberry32(env["seed"])
    K = env["keys"]
    weights = [1 / math.pow(r + 1, env["zipf"]) for r in range(K)]
    total = sum(weights)
    cdf, acc = [], 0.0
    for w in weights:
        acc += w / total
        cdf.append(acc)
    perm = list(range(K))
    shifted = [(k * 7 + 131) % K for k in range(K)]        # a different set of items becomes popular
    size, policy, ttl = s["size"], s["policy"], s["ttl"]
    store: "OrderedDict[int, Dict[str, Any]]" = OrderedDict()
    freq: Dict[int, int] = {}
    if env.get("warm"):                    # a freshly warmed cache: the most popular items were all loaded at the same instant
        for key in perm[:size]:
            exp = None if ttl == 0 else (max(1, int(round(ttl * (1 + (rg() - 0.5) * 1.0)))) if s["jitter"] else ttl)
            store[key] = {"exp": exp, "at": 0}
            freq[key] = 1
    hits = reqs = stale = 0
    lat_sum = 0.0
    overload_ticks = 0
    frames: List[Dict[str, Any]] = []
    spikes: List[int] = []
    for t in range(env["ticks"]):
        mapping = shifted if (env["shift_at"] is not None and t >= env["shift_at"]) else perm
        for key in list(store):
            if store[key]["exp"] is not None and store[key]["exp"] <= t:
                del store[key]
        seen, misses, rows = [], [], []
        for _ in range(env["rate"]):
            u = rg()
            lo, hi = 0, K - 1
            while lo < hi:
                mid = (lo + hi) // 2
                if cdf[mid] < u:
                    lo = mid + 1
                else:
                    hi = mid
            key = mapping[lo]
            reqs += 1
            if key in store:
                hits += 1
                if t - store[key]["at"] > env["fresh"]:
                    stale += 1                    # an answer older than the app is allowed to serve
                freq[key] = freq.get(key, 0) + 1
                if policy == "lru":
                    store.move_to_end(key)
                rows.append([key, 1])
            else:
                misses.append(key)
                rows.append([key, 0])
        unique = list(dict.fromkeys(misses)) if s["coalesce"] else misses
        db_load = len(unique)
        extra = max(0, db_load - env["db_cap"])
        miss_ms = env["miss_ms"] + 40.0 * extra / env["db_cap"]
        if extra:
            overload_ticks += 1
        spikes.append(db_load)
        lat_sum += (env["rate"] - len(misses)) * env["hit_ms"] + len(misses) * miss_ms
        for key in dict.fromkeys(misses):
            freq[key] = freq.get(key, 0) + 1
            exp = None
            if ttl > 0:
                exp = t + max(1, int(round(ttl * (1 + (rg() - 0.5) * 1.0)))) if s["jitter"] else t + ttl
            store[key] = {"exp": exp, "at": t}
            store.move_to_end(key)
            while len(store) > size:
                if policy == "lfu":
                    victim = min(store, key=lambda k: (freq.get(k, 0), 0))
                else:
                    victim = next(iter(store))          # fifo and lru both evict from the front of the order
                del store[victim]
        frames.append({"t": t, "reqs": rows, "slots": list(store.keys()), "db_load": db_load, "misses": len(misses),
                       "ratio": round(hits / reqs, 3), "avg_ms": round((lat_sum / reqs), 1)})
    hit_ratio = hits / max(1, reqs)
    avg_ms = lat_sum / max(1, reqs)
    peak = max(spikes) if spikes else 0
    stats = {"hit_ratio": round(hit_ratio, 3), "avg_ms": round(avg_ms, 1), "overload_ticks": overload_ticks, "peak_db": peak, "stale": round(stale / max(1, reqs), 3)}
    return {"frames": frames, "stats": stats, "insights": insights(env, s, stats)}


def insights(env: Dict[str, Any], s: Dict[str, Any], st: Dict[str, Any]) -> List[str]:
    out = [f"{st['hit_ratio'] * 100:.0f}% of requests were served from memory. The average response took {st['avg_ms']:.0f} ms."]
    if st["stale"] > 0.03:
        out.append(f"{st['stale'] * 100:.0f}% of answers were older than {env['fresh']} ticks. Data changes, so a cache needs a time to live (TTL) to refresh it.")
    if st["hit_ratio"] < 0.6 and s["size"] < env["max_slots"]:
        out.append("Many requests missed because the cache is small. A few popular items cover most traffic, so a bigger cache pays off quickly at first.")
    if st["overload_ticks"] > 3:
        out.append(f"The database was overloaded for {st['overload_ticks']} ticks (up to {st['peak_db']} lookups at once).")
        if s["ttl"] > 0 and not s["jitter"]:
            out.append("Items loaded together expire together. Spreading out the expiry times keeps the misses from arriving in waves.")
        if not s["coalesce"]:
            out.append("Merging duplicate misses means a popular item is fetched once instead of once per request.")
    if env["shift_at"] is not None and s["policy"] == "lfu":
        out.append("LFU keeps items that were popular for a long time, so it is slow to notice a trend change. LRU adapts faster.")
    if s["policy"] == "fifo":
        out.append("FIFO throws out the oldest item even if it is popular. LRU keeps recently used items, which usually works better.")
    return out


def badness(st: Dict[str, Any], env: Dict[str, Any]) -> float:
    return st["avg_ms"] + 0.5 * st["overload_ticks"] + 150 * st["stale"]
