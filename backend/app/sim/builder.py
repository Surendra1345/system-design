"""
Architecture builder simulator.

The player draws a graph of components and wires them together. We check the wiring,
work out what each component does, then run a deterministic traffic wave through it.
Deterministic means the server can replay a submitted design and decide the score itself.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

M32 = 0xFFFFFFFF


def mulberry32(seed: int):
    a = seed & M32

    def rng() -> float:
        nonlocal a
        a = (a + 0x6D2B79F5) & M32
        t = ((a ^ (a >> 15)) * (1 | a)) & M32
        t = ((t + (((t ^ (t >> 7)) * (61 | t)) & M32)) & M32) ^ t
        return ((t ^ (t >> 14)) & M32) / 4294967296

    return rng


COST = {"server": 10, "lb": 15, "cache": 20, "replica": 20, "cdn": 20, "queue": 15, "limiter": 10,
        "breaker": 10, "coalesce": 10, "autoscale": 25, "shard": 25}
SERVER_CAP = 40
READ_BASE, READ_PER_REPLICA = 70, 70
WRITE_BASE, WRITE_PER_SHARD = 30, 30
QUEUE_RATE, QUEUE_MAX = 25, 200
AUTOSCALE_COST, AUTOSCALE_MAX = 6, 10
HIT = [0, 0.35, 0.6, 0.8]

NODE_TYPES = {"client", "cdn", "limiter", "lb", "app", "cache", "queue", "db"}
# Which connections make sense. Anything else is rejected with a clear message.
ALLOWED_EDGES = {
    "client": {"cdn", "limiter", "lb", "app"},
    "cdn": {"limiter", "lb", "app"},
    "limiter": {"lb", "app"},
    "lb": {"app"},
    "app": {"cache", "db", "queue"},
    "cache": {"db"},
    "queue": {"db"},
    "db": set(),
}
LABEL = {"client": "Users", "cdn": "CDN", "limiter": "Rate limiter", "lb": "Load balancer", "app": "App servers",
         "cache": "Cache", "queue": "Queue", "db": "Database"}


def _int(v: Any, lo: int, hi: int, default: int) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def interpret(scenario: Dict[str, Any], design: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a design and turn it into the component counts the simulator uses."""
    errors: List[str] = []
    warnings: List[str] = []
    avail = set(scenario["avail"])
    base_servers = int((scenario.get("start") or {}).get("server", 1))

    nodes_in = design.get("nodes") or []
    edges_in = design.get("edges") or []
    if len(nodes_in) > 40 or len(edges_in) > 120:
        return {"valid": False, "errors": ["That design is too large."], "warnings": [], "comps": None, "cost": 0}

    nodes: Dict[str, Dict[str, Any]] = {}
    by_type: Dict[str, str] = {}
    for n in nodes_in:
        nid, typ = str(n.get("id", "")), n.get("type")
        if typ not in NODE_TYPES:
            errors.append("Unknown component: %s" % typ)
            continue
        if typ in by_type:
            errors.append("Only one %s is allowed. Use its settings to add more capacity." % LABEL[typ])
            continue
        nodes[nid] = {"type": typ, "params": n.get("params") or {}}
        by_type[typ] = nid

    for need, msg in (("client", "Add the Users node."), ("app", "Add App servers."), ("db", "Add a Database.")):
        if need not in by_type:
            errors.append(msg)
    for typ in by_type:
        key = {"cdn": "cdn", "limiter": "limiter", "lb": "lb", "cache": "cache", "queue": "queue"}.get(typ)
        if key and key not in avail:
            errors.append("%s is not available in this level." % LABEL[typ])

    adj: Dict[str, Set[str]] = {nid: set() for nid in nodes}
    for e in edges_in:
        s, t = str(e.get("source", "")), str(e.get("target", ""))
        if s not in nodes or t not in nodes:
            continue
        st, tt = nodes[s]["type"], nodes[t]["type"]
        if tt not in ALLOWED_EDGES[st]:
            errors.append("%s cannot connect directly to %s." % (LABEL[st], LABEL[tt]))
            continue
        adj[s].add(t)
    if errors:
        return {"valid": False, "errors": errors, "warnings": warnings, "comps": None, "cost": 0}

    def reach(start: str, graph: Dict[str, Set[str]], skip: Optional[str] = None) -> Set[str]:
        seen, stack = set(), [start]
        while stack:
            cur = stack.pop()
            if cur in seen or cur == skip:
                continue
            seen.add(cur)
            stack.extend(graph[cur])
        return seen

    rev: Dict[str, Set[str]] = {nid: set() for nid in nodes}
    for s, ts in adj.items():
        for t in ts:
            rev[t].add(s)
    client, app, db = by_type["client"], by_type["app"], by_type["db"]
    from_client, to_app = reach(client, adj), reach(app, rev)
    front = from_client & to_app                       # nodes on a path from users to the app
    app_reachable = app in from_client
    from_app = reach(app, adj)
    queue_id = by_type.get("queue")
    db_reachable = db in reach(app, adj, skip=queue_id)  # a database path that does not rely on the queue
    cache_id = by_type.get("cache")
    cache_on_path = bool(cache_id and cache_id in from_app and db in reach(cache_id, adj))

    if not app_reachable:
        errors.append("Users cannot reach the App servers. Connect them, directly or through a CDN, limiter or load balancer.")
    if not db_reachable:
        errors.append("App servers cannot reach the Database. Connect them directly or through a cache.")
    for typ, nid in by_type.items():
        if typ not in ("client", "app", "db") and not adj[nid] and not rev[nid]:
            warnings.append("%s is not connected, so it has no effect." % LABEL[typ])
    if errors:
        return {"valid": False, "errors": errors, "warnings": warnings, "comps": None, "cost": 0}

    p_app, p_cache, p_db = nodes[app]["params"], (nodes[cache_id]["params"] if cache_id else {}), nodes[db]["params"]
    instances = _int(p_app.get("instances"), base_servers, 8, base_servers)
    breaker, autoscale = bool(p_app.get("breaker")), bool(p_app.get("autoscale"))
    level = _int(p_cache.get("level"), 1, 3, 1) if cache_on_path else 0
    coalesce = bool(p_cache.get("coalesce")) and cache_on_path
    replicas = _int(p_db.get("replicas"), 0, 3, 0)
    shards = _int(p_db.get("shards"), 1, 4, 1)

    for flag, key, text in ((breaker, "breaker", "circuit breaker"), (autoscale, "autoscale", "auto scaling"),
                            (coalesce, "coalesce", "request coalescing"), (replicas > 0, "replica", "read replicas"),
                            (shards > 1, "shard", "extra shards"), (instances > base_servers, "server", "more app servers")):
        if flag and key not in avail:
            errors.append("%s is not available in this level." % text.capitalize())
    if errors:
        return {"valid": False, "errors": errors, "warnings": warnings, "comps": None, "cost": 0}

    comps = {
        "server": instances,
        "lb": 1 if ("lb" in by_type and by_type["lb"] in front) else 0,
        "cdn": 1 if ("cdn" in by_type and by_type["cdn"] in adj[client]) else 0,
        "limiter": 1 if ("limiter" in by_type and by_type["limiter"] in front) else 0,
        "cache": level, "coalesce": 1 if coalesce else 0,
        "queue": 1 if (queue_id and queue_id in adj[app]) else 0,
        "replica": replicas, "shard": shards - 1,
        "breaker": 1 if breaker else 0, "autoscale": 1 if autoscale else 0,
    }
    if instances > 1 and not comps["lb"]:
        warnings.append("Only one app server receives traffic without a load balancer in front.")
    cost = ((instances - base_servers) * COST["server"] + comps["lb"] * COST["lb"] + comps["cdn"] * COST["cdn"]
            + comps["limiter"] * COST["limiter"] + level * COST["cache"] + comps["coalesce"] * COST["coalesce"]
            + comps["queue"] * COST["queue"] + replicas * COST["replica"] + (shards - 1) * COST["shard"]
            + comps["breaker"] * COST["breaker"] + comps["autoscale"] * COST["autoscale"])
    # nodes the player placed but wired in a way that gives no benefit are still paid for in the design,
    # so cost counts only effective components. Warn about the rest above.
    if cost > scenario["budget"]:
        errors.append("This design costs %d coins but the budget is %d." % (cost, scenario["budget"]))
        return {"valid": False, "errors": errors, "warnings": warnings, "comps": comps, "cost": cost}
    return {"valid": True, "errors": [], "warnings": warnings, "comps": comps, "cost": cost}


def _segment(traffic: List[List[Any]], t: int) -> Dict[str, float]:
    r = {"read": 0.0, "write": 0.0, "static": 0.0, "job": 0.0, "abuse": 0.0}
    for lo, hi, vals in traffic:
        if lo <= t < hi:
            r.update(vals)
    return r


def _active(events: List[Dict[str, Any]], t: int, kind: str) -> bool:
    return any(e["type"] == kind and e["t"] <= t < e["t"] + e["dur"] for e in events)


def run(scenario: Dict[str, Any], comps: Dict[str, int], spent: int) -> Dict[str, Any]:
    rg = mulberry32(int(scenario.get("seed", 1)))
    c = dict(comps)
    events = scenario.get("events", [])
    backlog = 0.0
    last_util = 0.0
    good_sum = served_sum = 0.0
    frames: List[Dict[str, Any]] = []

    for t in range(int(scenario["ticks"])):
        tr = _segment(scenario["traffic"], t)

        def noise() -> float:
            return 1 + (rg() - 0.5) * 0.16

        rd, wr, stc, jb, ab = (tr["read"] * noise(), tr["write"] * noise(), tr["static"] * noise(),
                               tr["job"] * noise(), tr["abuse"] * noise())
        crash, hot, slow = _active(events, t, "crash"), _active(events, t, "hotkey"), _active(events, t, "depslow")

        if c["autoscale"] and last_util > 0.85 and c["server"] < AUTOSCALE_MAX and spent + AUTOSCALE_COST <= scenario["budget"]:
            c["server"] += 1
            spent += AUTOSCALE_COST
        alive = c["server"] - (1 if crash else 0)
        cap = max(0, alive) * SERVER_CAP if c["lb"] else (0 if crash else SERVER_CAP)
        if slow and not c["breaker"]:
            cap *= 0.4

        srv_static = 0 if c["cdn"] else stc
        abuse_pass = ab * 0.05 if c["limiter"] else ab
        hit = HIT[c["cache"]] * ((0.8 if c["coalesce"] else 0.3) if hot else 1) if c["cache"] else 0
        job_cost = 0.2 if c["queue"] else 4
        async_writes = slow and c["queue"]
        load = srv_static + rd + abuse_pass + wr + jb * job_cost
        srv_ok = min(1.0, cap / load) if load > 0 else 1.0

        read_cap = READ_BASE + READ_PER_REPLICA * c["replica"]
        write_cap = WRITE_BASE + WRITE_PER_SHARD * c["shard"]
        db_read = (rd + abuse_pass) * (1 - hit)
        db_read_ok = min(1.0, read_cap / db_read) if db_read > 0 else 1.0
        db_write_ok = min(1.0, write_cap / wr) if wr > 0 else 1.0

        s_static = stc if c["cdn"] else stc * srv_ok
        s_read = rd * (hit + (1 - hit) * db_read_ok) * srv_ok
        s_write = wr * db_write_ok * srv_ok
        if slow and c["breaker"] and not c["queue"]:
            s_write = 0.0
        if async_writes:
            s_write = wr * srv_ok
        s_job = jb * srv_ok
        if c["queue"]:
            backlog += s_job
            backlog = max(0.0, backlog - QUEUE_RATE)
            if backlog > QUEUE_MAX:
                s_job -= backlog - QUEUE_MAX
                backlog = float(QUEUE_MAX)

        good, served = rd + wr + stc + jb, s_static + s_read + s_write + s_job
        good_sum += good
        served_sum += served
        last_util = load / cap if cap > 0 else 2.0

        # What each individual server is doing, and where requests were lost. The live traffic view draws this.
        dynamic = srv_static + rd + wr + jb                 # legitimate requests that need the app servers
        lost_app = dynamic * (1 - srv_ok)
        lost_db = max(0.0, good - served - lost_app)
        stall = 0.4 if (slow and not c["breaker"]) else 1.0
        servers: List[Dict[str, Any]] = []
        for i in range(min(c["server"], 12)):
            if crash and i == 0:
                servers.append({"state": "dead", "util": 0.0})
            elif c["lb"] or i == 0:
                share = max(1, alive) if c["lb"] else 1
                u = (load / share) / (SERVER_CAP * stall)
                servers.append({"state": "hot" if u > 1 else "warm" if u > 0.7 else "ok", "util": round(min(2.0, u), 2)})
            else:
                servers.append({"state": "idle", "util": 0.0})   # no load balancer: only the first server gets traffic
        frames.append({
            "t": t, "good": round(good, 2), "served": round(served, 2), "ok": round(served / good if good else 1.0, 4),
            "events": [k for k, on in (("crash", crash), ("hotkey", hot), ("depslow", slow)) if on]
                      + (["abuse"] if tr["abuse"] else []),
            "nodes": {
                "client": {"load": round(good, 1)},
                "app": {"util": round(min(2.0, last_util), 3), "servers": c["server"], "alive": alive},
                "cache": {"hit": round(hit, 3)},
                "queue": {"backlog": round(backlog, 1)},
                "db": {"read": round(min(2.0, db_read / read_cap), 3), "write": round(min(2.0, wr / write_cap), 3)},
            },
            "spent": spent,
            "servers": servers,
            "flow": {"rate": round(good, 1), "static": round(stc if c["cdn"] else 0.0, 1), "dynamic": round(dynamic, 1), "abuse": round(ab, 1),
                     "blocked": round(ab - abuse_pass, 1), "lost_app": round(lost_app, 1), "lost_db": round(lost_db, 1)},
        })

    success = served_sum / good_sum if good_sum else 1.0
    stars = 0
    if success >= scenario["min"]:
        stars = 1
    if success >= 0.93:
        stars = 2
    if success >= 0.97 and spent <= scenario["par"]:
        stars = 3
    return {"frames": frames, "result": {"success": round(success, 4), "spent": spent, "stars": stars}}


def simulate(scenario: Dict[str, Any], design: Dict[str, Any]) -> Dict[str, Any]:
    info = interpret(scenario, design)
    out: Dict[str, Any] = {"valid": info["valid"], "errors": info["errors"], "warnings": info["warnings"], "cost": info["cost"],
                           "frames": [], "result": {"success": 0.0, "spent": info["cost"], "stars": 0}}
    if not info["valid"]:
        return out
    out.update(run(scenario, info["comps"], info["cost"]))
    out["comps"] = info["comps"]
    return out


def design_from_buys(scenario: Dict[str, Any], buys: List[str]) -> Dict[str, Any]:
    """Build a correctly wired design from a list of purchases. Used by tests and level hints."""
    n = lambda k: buys.count(k)
    base = int((scenario.get("start") or {}).get("server", 1))
    nodes = [{"id": "client", "type": "client"}]
    chain = ["client"]
    for key, typ in (("cdn", "cdn"), ("limiter", "limiter"), ("lb", "lb")):
        if n(key):
            nodes.append({"id": typ, "type": typ})
            chain.append(typ)
    nodes.append({"id": "app", "type": "app", "params": {"instances": base + n("server"), "breaker": bool(n("breaker")), "autoscale": bool(n("autoscale"))}})
    chain.append("app")
    edges = [{"source": a, "target": b} for a, b in zip(chain, chain[1:])]
    back = ["app"]
    if n("cache"):
        nodes.append({"id": "cache", "type": "cache", "params": {"level": n("cache"), "coalesce": bool(n("coalesce"))}})
        back.append("cache")
    nodes.append({"id": "db", "type": "db", "params": {"replicas": n("replica"), "shards": 1 + n("shard")}})
    back.append("db")
    edges += [{"source": a, "target": b} for a, b in zip(back, back[1:])]
    if n("queue"):
        nodes.append({"id": "queue", "type": "queue"})
        edges += [{"source": "app", "target": "queue"}, {"source": "queue", "target": "db"}]
    return {"nodes": nodes, "edges": edges}
