"""Load balancing lab: the same requests, different algorithms. Big requests pile up behind small ones when the algorithm is careless."""
from __future__ import annotations

from typing import Any, Dict, List

from .common import mulberry32, percentile, rng, sel, tog

KIND = "lb"
LEVELS: List[Dict[str, Any]] = [
    {"name": "Equal servers", "title": "Three equal servers, uneven requests", "seed": 11, "speeds": [7, 7, 7], "ticks": 50, "rate": 8, "noise": 2, "p_big": 0.15, "big": 8, "crashes": [],
     "brief": "Three identical servers share the traffic. Most requests are small, but a few are large. Pick how the load balancer chooses a server.", "goal": "Keep the slowest 5% of requests as quick as you can."},
    {"name": "Unequal servers", "title": "One big server and two small ones", "seed": 21, "speeds": [14, 7, 3], "ticks": 50, "rate": 8, "noise": 2, "p_big": 0.15, "big": 8, "crashes": [],
     "brief": "Your servers are different sizes: one is twice as fast as another and four times as fast as the smallest. A careless algorithm drowns the small server.", "goal": "Use each server according to its strength."},
    {"name": "A server dies", "title": "A server crashes in the middle of the rush", "seed": 31, "speeds": [8, 8, 8, 8], "ticks": 50, "rate": 12, "noise": 3, "p_big": 0.2, "big": 8,
     "crashes": [{"server": 0, "t": 15, "dur": 15}],
     "brief": "Four servers share a busy stream, and Server 1 crashes for a while. Requests sent to a dead server are lost, and the work it was doing is lost too.", "goal": "Lose nothing, and keep requests fast even with one server missing."},
]
ALGOS = [["round_robin", "Round robin"], ["random", "Random"], ["least_connections", "Least connections"], ["weighted", "Weighted round robin"], ["ip_hash", "IP hash (same client, same server)"]]


def controls(level: int) -> List[Dict[str, Any]]:
    env = LEVELS[level]
    c = [sel("algorithm", "Algorithm", ALGOS, "round_robin", "How the load balancer picks a server for each request.")]
    c += [rng("w%d" % i, "Weight of server %d" % (i + 1), 1, 6, 1, 1, "Only used by weighted round robin. A bigger weight sends more requests.") for i in range(len(env["speeds"]))]
    c.append(tog("health_checks", "Health checks", False, "Stop sending requests to a server that has crashed."))
    c.append(tog("sticky", "Sticky sessions", False, "Pin each client to the first server it used."))
    return c


def public_env(level: int) -> Dict[str, Any]:
    e = LEVELS[level]
    return {"speeds": e["speeds"], "ticks": e["ticks"], "crashes": e["crashes"], "big": e["big"]}


def run(env: Dict[str, Any], s: Dict[str, Any]) -> Dict[str, Any]:
    rg = mulberry32(env["seed"])
    speeds, n = env["speeds"], len(env["speeds"])
    weights = [s.get("w%d" % i, 1) for i in range(n)]
    queues: List[List[Dict[str, Any]]] = [[] for _ in range(n)]
    cur = [0] * n
    rr = 0
    pinned: Dict[int, int] = {}
    latencies: List[float] = []
    lost = done = 0
    served_units = [0.0] * n
    frames: List[Dict[str, Any]] = []
    nid = 0

    def dead(i: int, t: int) -> bool:
        return any(c["server"] == i and c["t"] <= t < c["t"] + c["dur"] for c in env["crashes"])

    for t in range(env["ticks"]):
        arrivals = []
        count = max(0, int(round(env["rate"] + (rg() - 0.5) * 2 * env["noise"])))
        for _ in range(count):
            big = rg() < env["p_big"]
            client = int(rg() * 20)
            size = env["big"] if big else 1
            alive = [i for i in range(n) if not dead(i, t)] if s["health_checks"] else list(range(n))
            nid += 1
            if not alive:
                lost += 1
                arrivals.append({"id": nid, "size": size, "server": -1})
                continue
            alg = s["algorithm"]
            if s["sticky"] and pinned.get(client) in alive:
                srv = pinned[client]
            elif alg == "round_robin":
                srv = alive[rr % len(alive)]
                rr += 1
            elif alg == "random":
                srv = alive[int(rg() * len(alive))]
            elif alg == "least_connections":
                srv = min(alive, key=lambda i: (len(queues[i]), i))
            elif alg == "weighted":
                total = sum(weights[i] for i in alive)
                for i in alive:
                    cur[i] += weights[i]
                srv = max(alive, key=lambda i: (cur[i], -i))
                cur[srv] -= total
            else:  # ip_hash
                srv = alive[client % len(alive)]
            if s["sticky"]:
                pinned.setdefault(client, srv)
            if dead(srv, t):
                lost += 1
                arrivals.append({"id": nid, "size": size, "server": srv, "lost": True})
                continue
            queues[srv].append({"id": nid, "size": float(size), "left": float(size), "arr": t})
            arrivals.append({"id": nid, "size": size, "server": srv})
        for i in range(n):
            if dead(i, t):
                lost += len(queues[i])
                queues[i] = []
                continue
            cap = float(speeds[i])
            while queues[i] and cap > 0:
                it = queues[i][0]
                w = min(cap, it["left"])
                it["left"] -= w
                cap -= w
                served_units[i] += w
                if it["left"] <= 1e-9:
                    latencies.append(t - it["arr"] + 1)
                    queues[i].pop(0)
                    done += 1
        frames.append({"t": t, "arrivals": arrivals, "queues": [[round(x["left"], 1) for x in q[:14]] for q in queues],
                       "qlen": [len(q) for q in queues], "dead": [dead(i, t) for i in range(n)], "done": done, "lost": lost})
    for i in range(n):  # requests still waiting at the end count with the time they have waited so far
        for it in queues[i]:
            latencies.append(env["ticks"] - it["arr"] + 1)
    total_units = sum(served_units) or 1.0
    cap_total = float(sum(speeds))
    share = [served_units[i] / total_units for i in range(n)]
    cap_share = [speeds[i] / cap_total for i in range(n)]
    stats = {"p95": percentile(latencies, 95), "avg": sum(latencies) / max(1, len(latencies)), "lost": lost, "done": done,
             "max_queue": max(f["qlen"][i] for f in frames for i in range(n)), "share": [round(x, 3) for x in share], "cap_share": [round(x, 3) for x in cap_share]}
    return {"frames": frames, "stats": stats, "insights": insights(env, s, stats)}


def insights(env: Dict[str, Any], s: Dict[str, Any], st: Dict[str, Any]) -> List[str]:
    out = [f"The slowest 5% of requests waited {st['p95']:.0f} ticks or more. {st['done']} requests finished and {st['lost']} were lost."]
    over = [(i, st["share"][i] / st["cap_share"][i]) for i in range(len(st["share"])) if st["cap_share"][i] > 0]
    worst = max(over, key=lambda x: x[1])
    if worst[1] > 1.35:
        out.append(f"Server {worst[0] + 1} did {st['share'][worst[0]] * 100:.0f}% of the work but is only {st['cap_share'][worst[0]] * 100:.0f}% of the capacity, so its queue grew. Try weights, or least connections.")
    if st["lost"] and not s["health_checks"] and env["crashes"]:
        out.append("Some requests were sent to a crashed server and lost. Health checks stop that.")
    if s["algorithm"] == "round_robin" and len(set(env["speeds"])) == 1 and st["p95"] > 4:
        out.append("Round robin deals requests out in turn without looking at how busy each server is, so a large request can sit in front of many small ones. Least connections avoids that.")
    if s["sticky"]:
        out.append("Sticky sessions pin each client to one server, which can leave one server busier than the others.")
    if s["algorithm"] == "least_connections" and st["p95"] <= 4:
        out.append("Least connections sends each new request to the server with the shortest queue, which keeps large and small requests spread out.")
    return out


def badness(st: Dict[str, Any], env: Dict[str, Any]) -> float:
    return st["p95"] + 0.4 * st["lost"]
