"""Journey lab: where do the milliseconds go when a page loads? Every round trip you remove is felt by every user."""
from __future__ import annotations

from typing import Any, Dict, List

from .common import sel, tog

KIND = "journey"
LEVELS: List[Dict[str, Any]] = [
    {"name": "London to New York", "title": "A first visit across the Atlantic", "rtt": 56, "assets": 6, "server": 40, "dns": 30, "target": 450,
     "brief": "A visitor in London opens a shop hosted in New York. A round trip takes 56 ms. The page needs the HTML and six images, and every step before the first byte counts.", "goal": "Get the page fully loaded under 450 ms."},
    {"name": "Slow mobile network", "title": "A phone on a weak connection", "rtt": 120, "assets": 10, "server": 60, "dns": 60, "target": 1100,
     "brief": "The same page on a phone with a 120 ms round trip and ten images. Every round trip is now twice as expensive.", "goal": "Load it in under 1.1 seconds."},
    {"name": "Heavy page", "title": "Twenty files, one slow server", "rtt": 80, "assets": 20, "server": 120, "dns": 40, "target": 1400,
     "brief": "A heavy page with twenty files and a server that needs 120 ms to build the HTML. You cannot fix everything, so pick what removes the most waiting.", "goal": "Load it in under 1.4 seconds."},
]


def controls(level: int) -> List[Dict[str, Any]]:
    return [tog("dns_cached", "DNS answer already cached", False, "The browser or resolver remembers the address from an earlier visit."),
            sel("tls", "TLS version", [["1.2", "TLS 1.2 (two extra round trips)"], ["1.3", "TLS 1.3 (one extra round trip)"]], "1.2", "The encryption handshake."),
            sel("http", "HTTP version", [["h1", "HTTP/1.1 (six connections, each set up separately)"], ["h2", "HTTP/2 (one connection for everything)"], ["h3", "HTTP/3 over QUIC (set-up in one round trip)"]], "h1", "How the files travel."),
            tog("cdn", "Serve the images from a CDN near the user", False, "The images come from a nearby edge with a 10 ms round trip, but it is a different host."),
            tog("preconnect", "Open connections early (preconnect)", False, "The browser sets up the image host connection while the HTML is still loading.")]


def public_env(level: int) -> Dict[str, Any]:
    e = LEVELS[level]
    return {"rtt": e["rtt"], "assets": e["assets"], "target": e["target"]}


def run(env: Dict[str, Any], s: Dict[str, Any]) -> Dict[str, Any]:
    rtt, n = env["rtt"], env["assets"]
    segs: List[Dict[str, Any]] = []
    t = 0.0

    def add(name: str, dur: float, kind: str, start: float = None) -> float:
        st = t if start is None else start
        segs.append({"name": name, "start": round(st, 1), "dur": round(dur, 1), "kind": kind})
        return st + dur

    if not s["dns_cached"]:
        t = add("DNS lookup", env["dns"], "setup")
    tls_rtts = 2 if s["tls"] == "1.2" else 1
    setup_rtts = 1 if s["http"] == "h3" else 1 + tls_rtts
    t = add("Connect and encrypt", setup_rtts * rtt, "setup")
    t = add("Request the page", rtt + env["server"], "wait")
    html_done = t
    host_rtt = 10 if s["cdn"] else rtt
    asset_start = html_done
    if s["cdn"]:
        extra_dns = 0 if s["dns_cached"] else env["dns"]
        cdn_setup = (extra_dns + (1 if s["http"] == "h3" else 1 + tls_rtts) * host_rtt)
        if s["preconnect"]:
            cdn_setup_start = 0.0                                   # set up while the HTML is still loading
            cdn_ready = cdn_setup_start + cdn_setup + (rtt if False else 0)
            asset_start = max(html_done, cdn_ready)
            add("Connect to the image host (early)", cdn_setup, "setup", 0.0)
        else:
            asset_start = html_done + cdn_setup
            add("Connect to the image host", cdn_setup, "setup", html_done)
    per_asset = host_rtt + 10
    if s["http"] == "h1":
        conn_setup = 0 if s["cdn"] else (1 + tls_rtts) * host_rtt
        batches = (n + 5) // 6
        end = asset_start
        for b in range(batches):
            batch_start = end
            end = add(f"Images {b * 6 + 1} to {min(n, b * 6 + 6)}" + ("" if not conn_setup else " (new connections)"), conn_setup + per_asset, "download", batch_start)
    else:
        end = add(f"All {n} images over one connection", host_rtt + 10 * min(n, 20) * 0.5, "download", asset_start)
    total = end
    setup_total = sum(x["dur"] for x in segs if x["kind"] == "setup" and x["start"] >= 0)
    stats = {"total": round(total), "target": env["target"], "met": total <= env["target"], "round_trips": round((total - env["server"]) / rtt, 1)}
    return {"frames": [{"t": i, "segments": segs[: i + 1]} for i in range(len(segs))], "segments": segs, "stats": stats, "insights": insights(env, s, stats, segs)}


def insights(env: Dict[str, Any], s: Dict[str, Any], st: Dict[str, Any], segs: List[Dict[str, Any]]) -> List[str]:
    out = [f"The page was fully loaded after {st['total']} ms, and the goal was {st['target']} ms. {'You made it.' if st['met'] else 'It is too slow.'}"]
    setup = sum(x["dur"] for x in segs if x["kind"] == "setup")
    out.append(f"{setup:.0f} ms went on setting up (looking up names and opening encrypted connections), before any useful data moved.")
    if s["tls"] == "1.2":
        out.append("TLS 1.3 needs one round trip to set up where TLS 1.2 needs two, so it saves a full round trip on every new connection.")
    if s["http"] == "h1" and env["assets"] > 6:
        out.append("HTTP/1.1 opens several connections and sets each one up separately. HTTP/2 and HTTP/3 send everything over one.")
    if s["cdn"] and not s["dns_cached"]:
        out.append("A CDN brings the images close, but it is another hostname, so it costs another lookup and connection. Preconnect hides some of that.")
    if not s["cdn"]:
        out.append("Every image travels the long way to the origin. A CDN shortens each of those trips.")
    return out


def badness(st: Dict[str, Any], env: Dict[str, Any]) -> float:
    return st["total"] / 10.0
