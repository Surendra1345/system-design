"""CDN lab: place edge servers on a world map so users are close to one, without overloading the origin."""
from __future__ import annotations

import math
from typing import Any, Dict, List

from .common import rng, sel, tog

KIND = "cdn"
REGIONS = [("na_w", "North America West", (14, 22), 18), ("na_e", "North America East", (27, 21), 24), ("sa", "South America", (33, 40), 8), ("eu", "Europe", (50, 17), 22),
           ("af", "Africa", (52, 34), 5), ("in", "India", (67, 28), 12), ("as", "East Asia", (80, 21), 20), ("oc", "Oceania", (88, 43), 4)]
SITES = [("na_w", "San Francisco", (14, 22)), ("na_e", "New York", (27, 21)), ("sa", "Sao Paulo", (33, 40)), ("eu", "Frankfurt", (50, 17)), ("af", "Lagos", (52, 34)),
         ("me", "Dubai", (60, 27)), ("in", "Mumbai", (67, 28)), ("sg", "Singapore", (76, 36)), ("as", "Tokyo", (80, 21)), ("oc", "Sydney", (88, 43))]
ORIGIN = (27, 21)  # the origin server is in New York
EDGE_COST, SHIELD_COST = 15, 20
LEVELS: List[Dict[str, Any]] = [
    {"name": "First edges", "title": "Bring the content closer", "budget": 45, "origin_cap": 450, "spikes": {}, "traffic": 1000,
     "brief": "All your content sits on one origin server in New York. Users on other continents wait for every byte to travel. You can afford a few edge servers.", "goal": "Cut the delay for most of your users."},
    {"name": "A premiere", "title": "A premiere floods one region", "budget": 60, "origin_cap": 330, "spikes": {"in": 3.0, "as": 1.8}, "traffic": 1000,
     "brief": "A premiere sends three times the usual traffic from India and more from East Asia. Edge servers also protect the origin from the extra load.", "goal": "Stay fast for everyone without overloading the origin."},
    {"name": "Tight budget", "title": "Everywhere at once, with little money", "budget": 80, "origin_cap": 240, "spikes": {"eu": 1.6, "in": 2.0, "as": 2.2}, "traffic": 1200,
     "brief": "Traffic is high from several regions and the origin can handle little. Choose edges carefully, and decide if an origin shield is worth its cost.", "goal": "Spend the budget where it removes the most delay."},
]


def controls(level: int) -> List[Dict[str, Any]]:
    return [{"id": "sites", "label": "Edge locations", "type": "multi", "options": [[sid, name] for sid, name, _ in SITES], "default": [], "max": 8,
             "help": "Each edge costs %d coins. Pick the places that are far from New York and have many users." % EDGE_COST},
            sel("ttl", "How long edges keep content", [["short", "Short (content changes often)"], ["long", "Long (content rarely changes)"]], "short", "Longer means fewer trips back to the origin."),
            tog("shield", "Origin shield (%d coins)" % SHIELD_COST, False, "One extra cache layer in front of the origin that merges requests from all edges.")]


def public_env(level: int) -> Dict[str, Any]:
    e = LEVELS[level]
    return {"budget": e["budget"], "origin_cap": e["origin_cap"], "edge_cost": EDGE_COST, "shield_cost": SHIELD_COST, "origin": list(ORIGIN),
            "regions": [{"id": r[0], "name": r[1], "pos": list(r[2]), "weight": r[3] * e["spikes"].get(r[0], 1.0)} for r in REGIONS],
            "sites": [{"id": s[0], "name": s[1], "pos": list(s[2])} for s in SITES]}


def _d(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def run(env: Dict[str, Any], s: Dict[str, Any]) -> Dict[str, Any]:
    chosen = [x for x in SITES if x[0] in s["sites"]]
    cost = len(chosen) * EDGE_COST + (SHIELD_COST if s["shield"] else 0)
    hit = 0.92 if s["ttl"] == "long" else 0.75
    shield_factor = 0.4 if s["shield"] else 1.0
    weights = {r[0]: r[3] * env["spikes"].get(r[0], 1.0) for r in REGIONS}
    wsum = sum(weights.values())
    rows, origin_load = [], 0.0
    for rid, name, pos, _ in REGIONS:
        share = weights[rid] / wsum
        traffic = env["traffic"] * share
        to_origin = 10 + _d(pos, ORIGIN) * 1.6
        if chosen:
            edge = min(chosen, key=lambda x: _d(pos, x[2]))
            e_lat = 10 + _d(pos, edge[2]) * 1.6
            miss_lat = e_lat + 10 + _d(edge[2], ORIGIN) * 1.6 + (12 if s["shield"] else 0)
            lat = hit * e_lat + (1 - hit) * miss_lat
            origin_load += traffic * (1 - hit) * shield_factor
            rows.append({"region": rid, "name": name, "share": round(share, 3), "edge": edge[0], "edge_name": edge[1], "latency": round(lat, 1), "direct": round(to_origin, 1)})
        else:
            origin_load += traffic
            rows.append({"region": rid, "name": name, "share": round(share, 3), "edge": None, "edge_name": None, "latency": round(to_origin, 1), "direct": round(to_origin, 1)})
    overload = max(0.0, origin_load / env["origin_cap"] - 1.0)
    for r in rows:
        r["latency"] = round(r["latency"] + 160 * overload, 1)
    ordered = sorted(rows, key=lambda r: r["latency"])
    acc, p75 = 0.0, ordered[-1]["latency"]
    for r in ordered:
        acc += r["share"]
        if acc >= 0.75:
            p75 = r["latency"]
            break
    avg = sum(r["latency"] * r["share"] for r in rows)
    stats = {"p75": round(p75, 1), "avg": round(avg, 1), "origin_load": round(origin_load), "origin_cap": env["origin_cap"], "cost": cost, "over_budget": cost > env["budget"], "overload": round(overload, 2)}
    frames = [{"t": i, "region": r} for i, r in enumerate(rows)]
    return {"frames": frames, "stats": stats, "insights": insights(env, s, stats, rows)}


def insights(env: Dict[str, Any], s: Dict[str, Any], st: Dict[str, Any], rows: List[Dict[str, Any]]) -> List[str]:
    out = [f"Three quarters of users get a response in {st['p75']:.0f} ms or less. The origin carries {st['origin_load']} requests a second and can handle {st['origin_cap']}."]
    if st["over_budget"]:
        out.append(f"This costs {st['cost']} coins and the budget is {env['budget']}. Remove an edge or the shield.")
    if st["overload"] > 0:
        out.append("The origin is overloaded, which slows down every response. More edges, longer caching or the origin shield reduce the load on it.")
    far = max(rows, key=lambda r: r["latency"] * r["share"])
    if not s["sites"]:
        out.append("With no edges, every request travels all the way to New York.")
    elif far["edge"] is not None and far["latency"] > 120:
        out.append(f"{far['name']} still waits {far['latency']:.0f} ms. It is far from every edge you chose.")
    if s["ttl"] == "short" and st["origin_load"] > st["origin_cap"] * 0.7:
        out.append("Edges with short caching keep asking the origin for fresh copies. If your content changes rarely, keep it longer.")
    return out


def badness(st: Dict[str, Any], env: Dict[str, Any]) -> float:
    return st["p75"] + (500 if st["over_budget"] else 0) + 50 * st["overload"]
