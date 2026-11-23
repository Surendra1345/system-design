"""
Builds the harder levels for every game from each lesson's first level.

    python tools/make_levels.py

Builder levels: same idea, more traffic, more things going wrong, a tighter budget. A solver searches for the
cheapest design that survives, so every level is proven winnable and the "efficient" target is realistic.
Incident levels: two unrelated failures at once, so the player must find and fix both.
Interview levels: a second, different question for the same topic.

The script is safe to re-run. It always starts from the first level in each file.
"""
from __future__ import annotations

import copy
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.sim import builder  # noqa: E402

CONTENT = ROOT / "app" / "content"
KEYS = ["logs", "metrics", "traces", "deploys", "deps"]


def load(name):
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def first(value):
    return value[0] if isinstance(value, list) else value


# ---------------------------------------------------------------- builder levels
def combos(sc):
    """Every purchase list the level allows, cheapest first."""
    avail = set(sc["avail"])
    base = int((sc.get("start") or {}).get("server", 1))
    ranges = {"server": range(0, 9 - base), "lb": range(2), "cache": range(4), "coalesce": range(2), "replica": range(4),
              "cdn": range(2), "queue": range(2), "limiter": range(2), "breaker": range(2), "autoscale": range(2), "shard": range(4)}
    names = [k for k in ranges if k in avail]
    out = []
    for counts in itertools.product(*[ranges[k] for k in names]):
        buys = [k for k, c in zip(names, counts) for _ in range(c)]
        if "coalesce" in buys and "cache" not in buys:
            continue
        cost = sum(builder.COST[b] for b in buys)
        out.append((cost, buys))
    out.sort(key=lambda x: (x[0], len(x[1])))
    return out


def solve(sc, want=0.975):
    big = copy.deepcopy(sc)
    big["budget"] = 1000
    for cost, buys in combos(sc):
        r = builder.simulate(big, builder.design_from_buys(big, buys))
        if r["valid"] and r["result"]["success"] >= want:
            return r["result"]["spent"], buys     # the simulated spend includes anything bought mid-test, such as auto scaling
    return None


def rounded(n, step=5):
    return int(-(-n // step) * step)


def harder(base, level, mult, extras, name, title_suffix, brief_add):
    sc = copy.deepcopy(base)
    sc["traffic"] = [[a, b, {k: (v if k == "abuse" else round(v * mult)) for k, v in vals.items()}] for a, b, vals in base["traffic"]]
    avail = set(base["avail"])
    events = list(base["events"])
    notes = []
    if "crash" in extras:
        events += [{"t": 22, "type": "crash", "dur": 10}] if level == 2 else [{"t": 6, "type": "crash", "dur": 8}, {"t": 24, "type": "crash", "dur": 10}]
        notes.append("a server will crash" if level == 2 else "servers will crash twice")
    if "hotkey" in extras and "cache" in avail:
        events.append({"t": 14, "type": "hotkey", "dur": 10})
        notes.append("a popular cache key will expire")
    if "depslow" in extras and "breaker" in avail:
        events.append({"t": 16, "type": "depslow", "dur": 14})
        notes.append("a dependency will slow down")
    if "abuse" in extras and "limiter" in avail:
        sc["traffic"].append([10, 30, {"abuse": round(90 * mult)}])
        notes.append("an abusive client will flood you")
    sc["events"] = events
    sc["level"], sc["name"] = level, name
    sc["title"] = base["title"] + ": " + title_suffix
    pct = round((mult - 1) * 100)
    sc["brief"] = "%s %s Traffic is %d%% higher%s." % (base["brief"], brief_add, pct, (" and " + ", ".join(notes)) if notes else "")
    return sc


def builder_levels(lesson, base):
    levels = [dict(base, level=1, name="Warm-up")]
    specs = [(2, 1.4, {"crash", "hotkey"}, "Rush hour", "rush hour", "Now it gets harder."),
             (3, 1.8, {"crash", "hotkey", "depslow", "abuse"}, "Perfect storm", "perfect storm", "Now everything goes wrong at once, and money is tight.")]
    for level, mult, extras, name, suffix, add in specs:
        m = mult
        while m >= 1.1:
            sc = harder(base, level, m, extras, name, suffix, add)
            found = solve(sc)
            if found:
                cost, buys = found
                sc["par"] = rounded(cost + 10)
                sc["budget"] = max(sc["par"] + 40, rounded(sc["par"] * 1.5))
                sc["solution"] = [{"t": 0, "buy": b} for b in buys]
                sc["min"] = 0.8
                check = builder.simulate(sc, builder.design_from_buys(sc, buys))
                assert check["valid"] and check["result"]["stars"] == 3, (lesson, level, check["result"], check["errors"])
                empty = builder.simulate(sc, builder.design_from_buys(sc, []))
                assert empty["result"]["stars"] == 0, (lesson, level, "doing nothing should fail")
                levels.append(sc)
                print("  %-12s L%d  traffic x%.1f  min cost %3d  par %3d  budget %3d  solution: %s" % (lesson, level, m, cost, sc["par"], sc["budget"], ", ".join(buys) or "(nothing)"))
                break
            m = round(m - 0.1, 2)
        else:
            print("  %-12s L%d  skipped: no affordable design survives" % (lesson, level))
    return levels


# ---------------------------------------------------------------- incident levels: two failures at once
def compound(lesson, a, partner_lesson, b):
    out = {"lesson": lesson, "id": a["id"] + "+" + b["id"], "level": 2, "name": "Double trouble"}
    out["title"] = "Double trouble: " + a["title"] + ", and " + b["title"][0].lower() + b["title"][1:]
    out["brief"] = "Two separate things are broken at the same time. First: %s Second: %s" % (a["brief"], b["brief"])
    out["clues"] = {k: "%s ALSO: %s" % (a["clues"][k], b["clues"][k]) for k in KEYS}
    acts, labels = [], set()
    for prefix, inc in (("a_", a), ("b_", b)):
        for act in inc["acts"]:
            if act[2] in labels:
                continue
            labels.add(act[2])
            acts.append([prefix + act[0]] + list(act[1:]))
    out["acts"] = acts
    ids = {x[0] for x in acts}
    out["need"] = [p + n for p, inc in (("a_", a), ("b_", b)) for n in inc["need"]]
    assert all(n in ids for n in out["need"]), (lesson, partner_lesson)
    out.update(par=9, max=16, start=55, rise=6)
    out["learn"] = a["learn"] + " " + b["learn"]
    return out


# ---------------------------------------------------------------- second interview questions
def r(point, *kw):
    return {"point": point, "keywords": list(kw)}


SECOND_INTERVIEWS = {
    "req": ("Payments and notifications across a broken link", "Two services in different data centres lose their connection for ten minutes: a payments service and a notifications service. Explain what each should do while the link is down, and how you make sure nothing is lost or duplicated afterwards.",
            [r("Payments avoid guessing and stay correct (refuse or queue as pending)", "refuse", "queue", "pending", "not charge", "wait"), r("Notifications keep working (availability first)", "availab", "keep sending", "buffer", "retry later"),
             r("Uses idempotency or de-duplication", "idempoten", "dedupe", "duplicate", "unique id", "request id"), r("Reconciles after the link returns", "reconcil", "replay", "catch up", "sync", "compare"), r("Detects the problem with monitoring or alerts", "alert", "monitor", "metric", "detect")]),
    "db": ("Stores for a fitness app", "A fitness app stores workouts, a social feed of friends' activity, and a leaderboard that updates every few seconds. Choose stores and explain how data moves between them.",
           [r("A durable relational source of truth for workouts", "postgres", "relational", "source of truth", "sql", "durable"), r("An in-memory store such as Redis sorted sets for the leaderboard", "redis", "sorted set", "in-memory", "leaderboard"),
            r("A precomputed or cached feed", "feed", "fan-out", "timeline", "precompute", "cache"), r("Moves data between stores with events, queues or change data capture", "event", "queue", "kafka", "change data capture", "cdc", "pipeline"), r("Accepts that derived stores can lag", "eventual", "stale", "lag", "consisten")]),
    "datatypes": ("Stores for a smart city", "A smart-city project collects traffic-camera images, bus GPS positions every second, citizen complaints as free text, and a map of roads. Choose a store for each and justify it.",
                  [r("A time-series or wide-column store for GPS positions", "time-series", "time series", "timescale", "cassandra", "wide-column", "influx"), r("Object storage for images", "object storage", "s3", "blob"),
                   r("A search engine for free-text complaints", "elasticsearch", "opensearch", "search engine", "full-text", "full text"), r("A graph or spatial store for the road map", "graph", "postgis", "spatial", "geo"), r("Keeps metadata or references in a database", "metadata", "reference", "index", "database")]),
    "cap": ("The last item in two regions", "Your shopping site runs in two regions. During a network split between them, a customer in each region tries to buy the very last item. Explain the options and pick one.",
            [r("Names the risk of selling it twice", "oversell", "last item", "twice", "both", "double"), r("Describes a consistent option (single leader, quorum or refusing one sale)", "leader", "quorum", "reject", "refuse", "single region", "consisten"),
             r("Describes an available option and how to fix it later (apologise, back-order, compensate)", "accept", "apolog", "compensat", "backorder", "back-order", "cancel", "reconcil"), r("Connects the choice to partitions and CAP", "partition", "cap"), r("Justifies the choice with a business cost", "business", "cost", "refund", "customer", "trade-off")]),
    "apistyles": ("APIs for a delivery company", "A food delivery company has a driver app that needs live location updates, a restaurant dashboard that shows orders with many details, and a public API for partners. Choose API styles and justify each.",
                  [r("Streaming for live driver location (WebSocket, gRPC streaming or server-sent events)", "websocket", "streaming", "grpc", "server-sent", "sse"), r("GraphQL for the detail-heavy dashboard", "graphql"), r("REST for the public partner API", "rest"),
                   r("Plans for versioning and backward compatibility", "version", "backward", "compatib"), r("Protects the API with authentication and rate limits", "rate limit", "auth", "api key", "oauth", "token")]),
    "solid": ("Redesign a notification service", "You have a NotificationService with sendEmail, sendSms and sendPush and a growing if/else on channel. You will soon need WhatsApp, and you want to test the service without sending real messages. How do you redesign it?",
              [r("One interface with a class per channel (strategy)", "interface", "strategy", "channel class", "polymorph"), r("Adds WhatsApp without editing existing code (open/closed)", "open/closed", "open closed", "new class", "without changing", "extend", "add a new"),
               r("Injects the channel so tests can use a fake", "inject", "fake", "mock", "test double", "dependency"), r("Separates formatting from sending (single responsibility)", "single responsibility", "separate", "template", "formatter"), r("Avoids over-engineering", "over-engineer", "too many", "simple", "only when")]),
    "oop": ("Design an elevator system", "Design the classes for an elevator system in a building with several elevators. Cover the entities, how a request is assigned to an elevator, and one tricky edge case.",
            [r("Identifies the entities (Elevator, Request, Floor, Controller)", "elevator", "request", "controller", "floor", "button"), r("Models elevator states (idle, moving up, moving down)", "state", "idle", "moving", "direction"),
             r("Uses an assignment strategy (nearest, scheduling)", "strategy", "nearest", "scheduling", "assign", "algorithm"), r("Handles concurrent requests with a queue or locking", "queue", "concurren", "thread", "lock", "thread-safe"), r("Names a tricky edge case (overload, emergency stop, door)", "overload", "emergency", "door", "stuck", "capacity")]),
    "patterns": ("Undo and plugins in an editor", "A text editor needs undo and redo, and also lets users add many kinds of toolbar buttons from plugins. Which design patterns would you use and how?",
                 [r("Command pattern for undoable actions", "command pattern", "command", "undo stack", "execute"), r("Undo and redo stacks for history", "stack", "history", "redo"), r("A plugin interface, factory or registry for toolbar buttons", "plugin", "factory", "registry", "interface", "extension"),
                  r("Observer to keep the user interface updated", "observer", "notify", "subscribe", "listener"), r("Mentions a trade-off such as memory or complexity", "trade-off", "memory", "complexity", "over")]),
    "interview": ("Open a ride-hailing design", "You are asked to design a ride-hailing service like Uber. List the clarifying questions you would ask and the main components you would sketch first.",
                  [r("Asks clarifying questions about scope and requirements", "clarif", "ask", "scope", "requirements"), r("Handles live location with GPS, WebSockets or geospatial indexing", "location", "gps", "websocket", "real-time", "geohash", "quadtree"),
                   r("Includes a matching or dispatch service", "matching", "dispatch", "nearest", "match"), r("Includes payments and pricing", "payment", "pricing", "surge", "fare"), r("Estimates scale (users, drivers, requests per second)", "estimate", "scale", "per second", "drivers")]),
    "mvp": ("Scope a delivery marketplace", "A founder wants to launch a food-delivery marketplace in one city with a team of three. What do you build first, what do you buy instead of building, and what do you postpone?",
            [r("Builds the core order-to-delivery loop for one city first", "core loop", "order", "vertical slice", "one city", "manual"), r("Buys instead of builds (payments, maps, notifications)", "stripe", "payment provider", "buy", "third-party", "third party", "existing service", "maps api"),
             r("Postpones custom routing, microservices or other heavy parts", "postpone", "later", "skip", "not yet", "defer"), r("Runs some steps manually at first", "manual", "concierge", "by hand"), r("Measures with real users", "measure", "metrics", "feedback", "users", "learn")]),
}


def main():
    builder_src = load("builder.json")
    incident_src = load("incidents.json")
    interview_src = load("interviews.json")

    print("Builder levels")
    new_builder = {lesson: builder_levels(lesson, first(v)) for lesson, v in builder_src.items()}

    lessons_order = [l["id"] for l in load("lessons.json")["lessons"]]
    inc_lessons = [l for l in lessons_order if l in incident_src]
    new_inc = {}
    for i, lesson in enumerate(inc_lessons):
        a = first(incident_src[lesson])
        partner = inc_lessons[(i + 1) % len(inc_lessons)]
        b = first(incident_src[partner])
        new_inc[lesson] = [dict(a, level=1, name="One failure"), compound(lesson, a, partner, b)]

    new_iv = {}
    for lesson, v in interview_src.items():
        base = first(v)
        title, prompt, rubric = SECOND_INTERVIEWS[lesson]
        extra = {"title": title, "prompt": prompt, "tips": ["Explain your reasoning, not just the names."],
                 "rubric": [dict(id="p%d" % (i + 1), **p) for i, p in enumerate(rubric)], "level": 2, "name": "Second question"}
        new_iv[lesson] = [dict(base, level=1, name="First question"), extra]

    (CONTENT / "builder.json").write_text(json.dumps(new_builder, indent=1), encoding="utf-8")
    (CONTENT / "incidents.json").write_text(json.dumps(new_inc, indent=1), encoding="utf-8")
    (CONTENT / "interviews.json").write_text(json.dumps(new_iv, indent=1), encoding="utf-8")
    total = sum(len(v) for v in new_builder.values()) + sum(len(v) for v in new_inc.values()) + sum(len(v) for v in new_iv.values())
    print("\nbuilder lessons %d | incident lessons %d | interview lessons %d | total levels %d" % (len(new_builder), len(new_inc), len(new_iv), total))


if __name__ == "__main__":
    main()
