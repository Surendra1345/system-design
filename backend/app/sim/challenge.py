"""Unknown Problem Challenge: a system is in trouble, the learner is not told which lesson it belongs to.

They diagnose each symptom, buy fixes within a budget, and a model of the system shows what happens. Every fix has a side effect,
so the right answer depends on the business context. A seed changes the numbers, so no two attempts are the same.
"""
from __future__ import annotations

import itertools
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from .builder import mulberry32

# ---------------------------------------------------------------- measures: cost and what each does to each metric (a multiplier)
MEASURES: Dict[str, Dict[str, Any]] = {
    "replicas": {"name": "Add read replicas", "cost": 22, "text": "Copies of the database that answer reads.", "fx": {"cpu": 0.55, "stale": 1.6, "spend": 1.1},
                 "why": "Replicas share the reads, but a copy can lag the primary, so users can see old data."},
    "cache": {"name": "Cache hot reads in Redis", "cost": 16, "text": "Answer repeat reads from memory.", "fx": {"cpu": 0.35, "hot": 0.8, "stale": 2.2, "spend": 0.95},
              "why": "A cache removes most database reads, but cached copies go stale when the data changes."},
    "invalidate": {"name": "Invalidate cached data on every write", "cost": 6, "text": "Delete or refresh a cached item as soon as it changes.", "fx": {"stale": 0.15},
                   "why": "Invalidating on write keeps cached copies from staying wrong."},
    "hotkey": {"name": "Split the hot item (local copies, sharded counters)", "cost": 12, "text": "Spread one popular item over many nodes.", "fx": {"hot": 0.35, "cpu": 0.85},
               "why": "One key cannot be spread by hashing, so the hot item itself has to be split or copied."},
    "idempotency": {"name": "Idempotency keys on checkout and payment", "cost": 5, "text": "A repeated request returns the saved result instead of running twice.", "fx": {"dup": 0.03},
                    "why": "Retries are normal, so the operation must be safe to repeat."},
    "workers": {"name": "Add queue workers", "cost": 10, "text": "More consumers drain the queue faster.", "fx": {"queue": 0.25, "cpu": 1.15, "spend": 1.1},
                "why": "More workers drain the backlog, but they also hit the database harder and cost more."},
    "dlq": {"name": "Dead-letter queue with retry backoff", "cost": 4, "text": "Park failing jobs and retry with growing delays.", "fx": {"queue": 0.5},
            "why": "Broken jobs stop clogging the line, and backoff stops retries from piling on."},
    "autoscale": {"name": "Autoscaling with a cap", "cost": 14, "text": "Add servers when busy and remove them when quiet, up to a limit.", "fx": {"spend": 0.55, "cpu": 0.9, "queue": 0.8},
                  "why": "Capacity follows the load, so you stop paying for a peak all day, but it needs time to boot."},
    "ratelimit": {"name": "Rate limit per user", "cost": 5, "text": "Cap how many requests one client can send.", "fx": {"cpu": 0.85, "queue": 0.8, "dup": 0.7, "spend": 0.9},
                  "why": "Limits stop one client or bot from consuming the system."},
    "ryw": {"name": "Read-your-writes routing", "cost": 6, "text": "A user's own recent changes are read from the primary.", "fx": {"stale": 0.35},
            "why": "People notice when their own change disappears, so their recent writes are read from the source."},
    "strong": {"name": "Strongly consistent reads for critical data", "cost": 8, "text": "Read the important values from the primary, never from a copy.", "fx": {"stale": 0.02, "cpu": 1.1},
               "why": "Critical values such as balances must come from the source of truth, at the cost of more primary load."},
    "cdn": {"name": "CDN for public pages", "cost": 12, "text": "Serve static pages and images from the edge.", "fx": {"cpu": 0.85, "hot": 0.6, "stale": 1.15},
            "why": "Public content moves to the edge, which takes load off the origin, and it can be slightly out of date."},
    "bigdb": {"name": "Buy a much bigger database", "cost": 38, "text": "More CPU and memory for the one database.", "fx": {"cpu": 0.5, "spend": 1.35},
              "why": "It works, but it is the most expensive fix and does nothing for the other problems."},
    "batch": {"name": "Queue and batch the writes", "cost": 9, "text": "Absorb write spikes in a queue and write in batches.", "fx": {"cpu": 0.8, "queue": 1.35, "dup": 1.1},
              "why": "Batching smooths database writes, but work now waits in a queue and a retry can repeat a write."},
    "fanout": {"name": "Hybrid fan-out for huge accounts", "cost": 10, "text": "Push posts for ordinary accounts, pull for celebrities.", "fx": {"queue": 0.25, "hot": 0.5, "cpu": 0.8},
               "why": "Pushing one celebrity post to every follower is far too much work, so their posts are fetched when read."},
}

# ---------------------------------------------------------------- symptoms: what is wrong, and the real cause among tempting wrong ones
CAUSES: Dict[str, Dict[str, str]] = {
    "cpu": {"right": "Too many reads and writes land on one database", "explain": "The single database does all the work. Reads can be cached or copied, writes can be smoothed, and load can be limited."},
    "stale": {"right": "Cached or copied data is not refreshed when it changes", "explain": "Copies and caches lag the source. Invalidate on write, and read critical or recent data from the source."},
    "dup": {"right": "Retries repeat a request that is not safe to repeat", "explain": "A timeout and retry can run the same operation twice. Idempotency keys make a repeat harmless."},
    "hot": {"right": "One very popular key overloads one node", "explain": "Hashing cannot spread a single key. Split or copy the hot item, or serve it from the edge."},
    "queue": {"right": "Consumers cannot keep up and bad jobs block the line", "explain": "The backlog grows when workers are too few or failing jobs retry forever. Add workers, a dead-letter queue and backoff."},
    "spend": {"right": "Fixed capacity is sized for the peak all day", "explain": "Paying for the peak around the clock is the cost. Scale with the load and limit abuse."},
}
WRONG = {"cpu": ["The network is too slow", "The code needs a faster language", "The disks are too small"], "stale": ["The clocks on the servers are wrong", "The database lost data", "Users need to log in again"],
         "dup": ["The load balancer is broken", "The cache is too small", "The database has no index"], "hot": ["There are too few servers in total", "The CDN is switched off by mistake", "The database is out of disk"],
         "queue": ["The network cable is faulty", "The messages are too small", "The cache has expired"], "spend": ["The code has a memory leak", "Users are using too many features", "The database is too fast"]}

TEMPLATES: Dict[str, Dict[str, Any]] = {
    "flashsale": {"title": "The flash sale", "blurb": "A shop's biggest sale of the year, and everything hurts at once.",
                  "story": "A shopping platform with {users} users has started its biggest flash sale. Some pages are already cached. Orders are flooding in and several things are going wrong at the same time. You do not know which part of the system is to blame.",
                  "budget": 60, "measures": ["replicas", "cache", "invalidate", "hotkey", "idempotency", "workers", "dlq", "autoscale", "ratelimit", "ryw", "cdn", "bigdb", "batch"],
                  "symptoms": [("cpu", "The database CPU is at {v}%", 98, 75, "%"), ("stale", "Some users see old stock levels ({v}% of reads)", 12, 2, "%"), ("dup", "{v}% of checkouts are duplicated", 4, 0.5, "%"),
                               ("hot", "A single product gets {v}% of all traffic", 70, 40, "%"), ("queue", "The order queue is {v} minutes behind", 22, 3, " min"), ("spend", "Infrastructure spend is running at {v}% of plan", 150, 100, "%")],
                  "defend": [("tradeoff", "Names a side effect of a fix they chose (for example staleness, load or cost)", ["stale", "lag", "side effect", "trade", "cost", "expensive", "slower", "more load"]),
                             ("cache", "Explains how stale or old data is kept under control", ["invalidat", "ttl", "refresh", "read-your-writes", "own writes", "primary"]),
                             ("retry", "Explains why duplicates happen and how they are stopped", ["idempot", "retry", "retries", "unique key", "twice"]),
                             ("budget", "Relates the choices to the budget", ["budget", "cheap", "afford", "cost", "priorit"])]},
    "bank": {"title": "The bank statements", "blurb": "The same kind of trouble, but wrong data is worse than slow data.",
             "story": "A bank's mobile app has {users} users. Payday has arrived and the balance and statement service is struggling. Here a wrong number is much worse than a slow one, so think about which fixes are safe.",
             "budget": 64, "measures": ["replicas", "cache", "invalidate", "idempotency", "workers", "dlq", "autoscale", "ratelimit", "ryw", "strong", "bigdb", "batch"],
             "symptoms": [("cpu", "The database CPU is at {v}%", 96, 75, "%"), ("stale", "Customers see an old balance after a payment ({v}% of reads)", 8, 0.2, "%"), ("dup", "{v}% of payments are submitted twice", 3, 0.1, "%"),
                          ("queue", "Statement jobs are {v} minutes behind", 18, 3, " min"), ("spend", "Infrastructure spend is running at {v}% of plan", 130, 100, "%")],
             "defend": [("consistency", "Explains why the balance must come from the source of truth", ["consisten", "source of truth", "primary", "never stale", "balance"]),
                        ("tradeoff", "Names a trade-off of a fix they chose", ["stale", "lag", "trade", "cost", "expensive", "more load", "side effect"]),
                        ("retry", "Explains how duplicate payments are prevented", ["idempot", "unique key", "twice", "retry", "retries"]),
                        ("budget", "Relates the choices to the budget", ["budget", "cheap", "afford", "cost", "priorit"])]},
    "feed": {"title": "The celebrity post", "blurb": "One account with a huge audience posts, and the feed system buckles.",
             "story": "A social app with {users} users is trending. A celebrity just posted, and their followers are all opening the app at once. Slightly old posts are fine here, but the system is overloaded.",
             "budget": 52, "measures": ["replicas", "cache", "invalidate", "hotkey", "workers", "dlq", "autoscale", "ratelimit", "cdn", "batch", "fanout", "bigdb"],
             "symptoms": [("cpu", "The database CPU is at {v}%", 95, 75, "%"), ("hot", "One celebrity's post gets {v}% of all reads", 72, 40, "%"), ("queue", "The fan-out queue is {v} minutes behind", 40, 5, " min"),
                          ("stale", "Followers see the post {v} seconds late", 30, 25, " s"), ("spend", "Infrastructure spend is running at {v}% of plan", 160, 100, "%")],
             "defend": [("fanout", "Explains why pushing a celebrity's post to every follower is too expensive", ["fan-out", "fanout", "followers", "pull", "push", "millions"]),
                        ("tradeoff", "Names a trade-off of a fix they chose", ["stale", "lag", "trade", "cost", "expensive", "more load", "side effect", "late"]),
                        ("hot", "Explains how the hot item is handled", ["hot", "popular", "cache", "copy", "split", "celebrity"]),
                        ("budget", "Relates the choices to the budget", ["budget", "cheap", "afford", "cost", "priorit"])]},
}
USERS = ["120,000", "250,000", "500,000", "800,000", "1.2 million", "2 million"]


def evaluate_metrics(tpl: Dict[str, Any], base: Dict[str, float], chosen: List[str]) -> Dict[str, float]:
    out = dict(base)
    for m in chosen:
        for k, mult in MEASURES[m]["fx"].items():
            if k in out:
                out[k] *= mult
    return out


def _spec(template: str, seed: int) -> Dict[str, Any]:
    tpl = TEMPLATES[template]
    rg = mulberry32(seed * 7919 + len(template))
    scale = 0.9 + rg() * 0.2
    users = USERS[int(rg() * len(USERS))]
    syms = []
    for sid, text, base, th, unit in tpl["symptoms"]:
        b = round(base * (scale if sid not in ("dup", "stale") else (0.9 + rg() * 0.2)), 1)
        syms.append({"id": sid, "text": text, "base": b, "threshold": th, "unit": unit})
    return {"template": template, "seed": seed, "users": users, "budget": tpl["budget"] + int(round((scale - 1.0) * 30)), "symptoms": syms}


def feasible(template: str, spec: Dict[str, Any]) -> Optional[List[str]]:
    tpl = TEMPLATES[template]
    base = {s["id"]: s["base"] for s in spec["symptoms"]}
    best: Optional[Tuple[int, List[str]]] = None
    ids = tpl["measures"]
    for r in range(0, 9):
        for combo in itertools.combinations(ids, r):
            cost = sum(MEASURES[m]["cost"] for m in combo)
            if cost > spec["budget"] or (best and cost >= best[0]):
                continue
            met = evaluate_metrics(tpl, base, list(combo))
            if all(met[s["id"]] <= s["threshold"] for s in spec["symptoms"]):
                best = (cost, list(combo))
    return best[1] if best else None


@lru_cache(maxsize=512)
def generate(template: str, seed: int) -> Dict[str, Any]:
    """The same template and seed always give the same challenge. A seed that has no affordable solution is eased until one exists."""
    s = seed
    for _ in range(40):
        spec = _spec(template, s)
        if feasible(template, spec) is not None:
            spec["seed"] = seed
            return spec
        s += 1000
    raise RuntimeError("no feasible challenge")


def public(template: str, seed: int) -> Dict[str, Any]:
    spec, tpl = generate(template, seed), TEMPLATES[template]
    rg = mulberry32(seed + 5)
    syms = []
    for s in spec["symptoms"]:
        opts = [{"id": "right", "text": CAUSES[s["id"]]["right"]}] + [{"id": "w%d" % i, "text": t} for i, t in enumerate(WRONG[s["id"]])]
        opts.sort(key=lambda o: rg())
        syms.append({"id": s["id"], "text": s["text"].replace("{v}", str(s["base"])), "value": s["base"], "threshold": s["threshold"], "unit": s["unit"], "causes": opts})
    return {"id": template, "title": tpl["title"], "seed": seed, "story": tpl["story"].replace("{users}", spec["users"]), "budget": spec["budget"], "users": spec["users"], "symptoms": syms,
            "measures": [{"id": m, "name": MEASURES[m]["name"], "text": MEASURES[m]["text"], "cost": MEASURES[m]["cost"]} for m in tpl["measures"]],
            "defend": [d[1] for d in tpl["defend"]]}


def run(template: str, seed: int, diagnosis: Dict[str, str], chosen: List[str]) -> Dict[str, Any]:
    spec, tpl = generate(template, seed), TEMPLATES[template]
    chosen = [m for m in dict.fromkeys(chosen) if m in tpl["measures"]]
    cost = sum(MEASURES[m]["cost"] for m in chosen)
    base = {s["id"]: s["base"] for s in spec["symptoms"]}
    after = evaluate_metrics(tpl, base, chosen)
    rows, resolved = [], 0
    for s in spec["symptoms"]:
        ok = after[s["id"]] <= s["threshold"]
        resolved += ok
        rows.append({"id": s["id"], "text": s["text"].replace("{v}", str(s["base"])), "before": s["base"], "after": round(after[s["id"]], 2), "threshold": s["threshold"], "unit": s["unit"], "resolved": ok,
                     "worse": after[s["id"]] > s["base"] * 1.05})
    diag = []
    right = 0
    for s in spec["symptoms"]:
        ok = diagnosis.get(s["id"]) == "right"
        right += ok
        diag.append({"id": s["id"], "correct": ok, "answer": CAUSES[s["id"]]["right"], "explain": CAUSES[s["id"]]["explain"]})
    n = len(spec["symptoms"])
    within = cost <= spec["budget"]
    score = 50.0 * resolved / n + 30.0 * right / n + (20.0 if within else 0.0)
    stars = 3 if resolved == n and within and right / n >= 0.8 else 2 if resolved / n >= 0.8 and within and right / n >= 0.5 else 1 if resolved / n >= 0.5 or right / n >= 0.7 else 0
    notes = []
    for m in chosen:
        notes.append({"measure": MEASURES[m]["name"], "note": MEASURES[m]["why"]})
    harms = [r["text"] for r in rows if r["worse"]]
    return {"rows": rows, "diagnosis": diag, "cost": cost, "budget": spec["budget"], "over_budget": not within, "resolved": resolved, "total": n, "diag_right": right, "score": round(score, 1), "stars": stars,
            "notes": notes, "harms": harms, "chosen": chosen}


def defend_data(template: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """The rubric for the written defence, in the same shape the interview grader uses."""
    tpl = TEMPLATES[template]
    return {"title": tpl["title"], "prompt": "Explain the fixes you chose, what each one costs or risks, and why the others were not worth it. Chosen: " + ", ".join(MEASURES[m]["name"] for m in result["chosen"]),
            "tips": [], "rubric": [{"id": d[0], "point": d[1], "keywords": d[2]} for d in tpl["defend"]]}
