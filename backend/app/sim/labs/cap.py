"""CAP lab: three replicas, a network partition, and quorum settings. Choose between refusing requests and returning old or conflicting data."""
from __future__ import annotations

from typing import Any, Dict, List

from .common import mulberry32, rng, sel

KIND = "cap"
N, KEYS = 3, 6
LEVELS: List[Dict[str, Any]] = [
    {"name": "Shopping cart", "title": "A cart must always accept items", "seed": 2, "ticks": 60, "part": [20, 45], "iso": 2, "w": {"unavail": 100, "stale": 8, "lost": 60},
     "brief": "From tick 20 to 45 replica 3 is cut off from the other two. Customers must always be able to add to their cart, and a missing item loses a sale.", "goal": "Never refuse a customer, and never lose an item."},
    {"name": "Bank balance", "title": "A balance must never be wrong", "seed": 4, "ticks": 60, "part": [20, 45], "iso": 2, "w": {"unavail": 60, "stale": 250, "lost": 400},
     "brief": "The same partition, but now these are account balances. Showing an old balance or losing a deposit is far worse than saying 'try again'.", "goal": "Never show or lose wrong data, even if some requests are refused."},
    {"name": "Like counter", "title": "Counts that can be a little off", "seed": 6, "ticks": 60, "part": [20, 45], "iso": 0, "w": {"unavail": 200, "stale": 2, "lost": 3},
     "brief": "Replica 1 is cut off. These are like counts, so a slightly old number does not matter at all, but an error page would be embarrassing.", "goal": "Stay up. Nobody cares if a count is a few likes behind."},
]


def controls(level: int) -> List[Dict[str, Any]]:
    return [rng("w", "Replicas that must confirm a write (W)", 1, 3, 1, 3, "The write succeeds only if this many replicas accept it."),
            rng("r", "Replicas asked on a read (R)", 1, 3, 1, 3, "A read looks at this many replicas and returns the newest answer."),
            sel("conflict", "When both sides changed the same thing", [["lww", "Keep the latest, drop the other (last write wins)"], ["merge", "Merge both changes"]], "lww", "What happens when the partition heals.")]


def public_env(level: int) -> Dict[str, Any]:
    e = LEVELS[level]
    return {"n": N, "ticks": e["ticks"], "part": e["part"], "iso": e["iso"]}


def run(env: Dict[str, Any], s: Dict[str, Any]) -> Dict[str, Any]:
    rg = mulberry32(env["seed"])
    rep = [[0] * KEYS for _ in range(N)]                  # newest write number each replica has per key
    latest = [0] * KEYS
    seq = 0
    p0, p1 = env["part"]
    side_writes: List[Dict[int, int]] = [{}, {}]          # during the partition: key -> writes on (isolated, majority) side
    fails = ok_ops = stale = lost = 0
    frames: List[Dict[str, Any]] = []
    for t in range(env["ticks"]):
        part = p0 <= t < p1
        if t == p1:
            for k in range(KEYS):
                a, b = side_writes[0].get(k, 0), side_writes[1].get(k, 0)
                if a and b and s["conflict"] == "lww":
                    lost += min(a, b)
            side_writes = [{}, {}]
            for k in range(KEYS):
                m = max(rep[i][k] for i in range(N))
                for i in range(N):
                    rep[i][k] = m
        ops = []
        for o in range(9):
            kind = "w" if o < 3 else "r"
            c = int(rg() * N)
            k = int(rg() * KEYS)
            reach = [i for i in range(N) if not part or (i == env["iso"]) == (c == env["iso"])]
            need = s["w"] if kind == "w" else s["r"]
            if len(reach) < need:
                fails += 1
                ops.append([kind, c, 0, 0])
                continue
            ok_ops += 1
            if kind == "w":
                seq += 1
                latest[k] = seq
                for i in reach:
                    rep[i][k] = seq
                if part:
                    side = 0 if c == env["iso"] else 1
                    side_writes[side][k] = side_writes[side].get(k, 0) + 1
                ops.append(["w", c, 1, 0])
            else:
                asked = [c] + [i for i in reach if i != c][: need - 1]
                got = max(rep[i][k] for i in asked)
                st = got < latest[k]
                stale += 1 if st else 0
                ops.append(["r", c, 1, 1 if st else 0])
        frames.append({"t": t, "part": part, "ops": ops, "fresh": [sum(1 for k in range(KEYS) if rep[i][k] == latest[k]) for i in range(N)], "fails": fails, "stale": stale, "lost": lost})
    total = env["ticks"] * 9
    reads_ok = max(1, ok_ops * 2 // 3)
    stats = {"unavail_frac": round(fails / total, 3), "stale_frac": round(stale / reads_ok, 3), "lost": lost, "failed": fails, "w": s["w"], "r": s["r"]}
    return {"frames": frames, "stats": stats, "insights": insights(env, s, stats)}


def insights(env: Dict[str, Any], s: Dict[str, Any], st: Dict[str, Any]) -> List[str]:
    out = [f"{st['failed']} requests were refused, {st['stale_frac'] * 100:.0f}% of reads returned old data and {st['lost']} writes were lost."]
    if st["unavail_frac"] > 0.05:
        out.append("The cut-off replica cannot reach enough partners, so requests that land on it must be refused. You chose consistency over availability (CP).")
    if s["w"] + s["r"] <= 3 and st["stale_frac"] > 0.02:
        out.append("With W + R not greater than 3, a read may ask only replicas that missed the latest write. Make W + R at least 4 so reads and writes always overlap.")
    if st["lost"]:
        out.append("Both sides of the partition accepted changes to the same item. Keeping only the latest throws the other away. Merging keeps both.")
    if s["w"] == 1 and s["r"] == 1:
        out.append("W = 1 and R = 1 keeps every replica answering during the partition (AP), at the price of stale reads and conflicts.")
    return out


def badness(st: Dict[str, Any], env: Dict[str, Any]) -> float:
    w = LEVELS[0]["w"]
    for e in LEVELS:
        if e["seed"] == env["seed"]:
            w = e["w"]
    return w["unavail"] * st["unavail_frac"] + w["stale"] * st["stale_frac"] + w["lost"] * st["lost"] / 10 + 0.4 * (st["w"] + st["r"])
