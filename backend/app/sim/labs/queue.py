"""Queue lab: producers, a queue and workers. A spike, a poison message and a crash show why queues need care."""
from __future__ import annotations

from typing import Any, Dict, List

from .common import mulberry32, rng, tog

KIND = "queue"
LEVELS: List[Dict[str, Any]] = [
    {"name": "A spike", "title": "A sudden rush of jobs", "seed": 3, "ticks": 60, "base": 3, "spike": [15, 30, 9], "p_poison": 0.0, "crash": None, "max_workers": 12,
     "brief": "Jobs arrive steadily, then a rush of three times as many. Each worker finishes one job per tick. Too few workers and the queue grows without limit.", "goal": "Keep jobs from waiting long without paying for idle workers."},
    {"name": "A poison message", "title": "One job that always fails", "seed": 7, "ticks": 60, "base": 3, "spike": [15, 30, 7], "p_poison": 0.05, "crash": None, "max_workers": 12,
     "brief": "Some jobs are broken and fail every time. If the queue retries them forever, they clog the workers while good jobs wait.", "goal": "Isolate the broken jobs and keep the healthy ones flowing."},
    {"name": "A crash", "title": "A worker dies after doing the work", "seed": 17, "ticks": 60, "base": 3, "spike": [15, 30, 7], "p_poison": 0.05, "crash": 22, "max_workers": 12,
     "brief": "A worker crashes after it sends a customer an email but before it tells the queue the job is done. The queue sends the job again.", "goal": "Never act twice on the same job, even when delivery repeats."},
]


def controls(level: int) -> List[Dict[str, Any]]:
    mw = LEVELS[level]["max_workers"]
    return [rng("workers", "Workers", 1, mw, 1, 2, "Each worker finishes one job per tick.", ""),
            rng("retries", "Retries for a failed job", 0, 6, 1, 6, "How many times a failed job goes back in the queue. 6 means forever.", ""),
            tog("dlq", "Dead-letter queue", False, "After the last retry, park the job in a separate queue instead of dropping it or retrying forever."),
            tog("idempotent", "Safe to repeat (idempotent workers)", False, "A job that has already been done is recognised and skipped when it arrives again.")]


def public_env(level: int) -> Dict[str, Any]:
    e = LEVELS[level]
    return {"ticks": e["ticks"], "max_workers": e["max_workers"], "crash": e["crash"], "spike": e["spike"]}


def run(env: Dict[str, Any], s: Dict[str, Any]) -> Dict[str, Any]:
    rg = mulberry32(env["seed"])
    W, max_retry = s["workers"], s["retries"]
    unlimited = max_retry >= 6
    queue: List[Dict[str, Any]] = []
    workers: List[Any] = [None] * W
    dlq: List[Dict[str, Any]] = []
    nid = arrived = done = dups = lost_poison = 0
    max_age = 0
    frames: List[Dict[str, Any]] = []
    blocked_ticks = 0
    crash_pending = True
    for t in range(env["ticks"]):
        rate = env["base"]
        a, b, hi = env["spike"]
        if a <= t < b:
            rate = hi
        for _ in range(rate):
            nid += 1
            arrived += 1
            queue.append({"id": nid, "poison": rg() < env["p_poison"], "tries": 0, "arr": t})
        for i in range(W):
            job = workers[i]
            if job is None and queue:
                workers[i] = queue.pop(0)
                job = workers[i]
            if job is None:
                continue
            if crash_pending and env["crash"] is not None and t >= env["crash"] and not job["poison"]:
                # the worker did the work (the customer got the email) but died before telling the queue
                crash_pending = False
                job["effect"] = True
                queue.insert(0, job)
                workers[i] = None
                continue
            workers[i] = None
            if job["poison"]:
                job["tries"] += 1
                if unlimited or job["tries"] <= max_retry:
                    queue.append(job)
                elif s["dlq"]:
                    dlq.append(job)
                else:
                    lost_poison += 1
            else:
                if job.get("effect") and not s["idempotent"]:
                    dups += 1                       # the same job ran a second time, so the customer is contacted twice
                done += 1
                max_age = max(max_age, t - job["arr"] + 1)
        busy_poison = sum(1 for j in queue[:W] if j["poison"])
        if queue and busy_poison >= max(1, min(W, len(queue))) and any(not j["poison"] for j in queue):
            blocked_ticks += 1
        for j in queue:
            if not j["poison"]:
                max_age = max(max_age, t - j["arr"] + 1)
        frames.append({"t": t, "queue": [[1 if j["poison"] else 0, t - j["arr"]] for j in queue[:30]], "qlen": len(queue), "workers": [1 if w is not None else 0 for w in workers],
                       "dlq": len(dlq), "dups": dups, "done": done, "oldest": max((t - j["arr"] for j in queue if not j["poison"]), default=0)})
    legit_left = sum(1 for j in queue if not j["poison"])
    stats = {"done": done, "dups": dups, "max_age": max_age, "legit_left": legit_left, "dlq": len(dlq), "workers": W, "poison_in_queue": sum(1 for j in queue if j["poison"]),
             "blocked": blocked_ticks, "arrived": arrived}
    return {"frames": frames, "stats": stats, "insights": insights(env, s, stats)}


def insights(env: Dict[str, Any], s: Dict[str, Any], st: Dict[str, Any]) -> List[str]:
    out = [f"{st['done']} jobs were completed. The longest any healthy job waited was {st['max_age']} ticks, and {st['legit_left']} healthy jobs were still waiting at the end."]
    if st["max_age"] > 8 and s["workers"] < env["spike"][2]:
        out.append(f"During the rush {env['spike'][2]} jobs arrive each tick but only {s['workers']} workers are running, so the queue grows.")
    if env["p_poison"] and s["retries"] >= 6 and not s["dlq"]:
        out.append("Broken jobs are retried forever, so they keep taking worker time that healthy jobs need. Limit retries and use a dead-letter queue.")
    if st["dlq"]:
        out.append(f"{st['dlq']} broken jobs are parked in the dead-letter queue, where someone can look at them without slowing everything else.")
    if env["crash"] is not None and st["dups"]:
        out.append(f"After the crash the queue redelivered a job whose work was already done, so a customer was contacted twice ({st['dups']} duplicate). Make workers idempotent.")
    if env["crash"] is not None and s["idempotent"]:
        out.append("Workers recognised the repeated job and skipped it, so nothing happened twice.")
    if s["workers"] > env["spike"][2] + 1:
        out.append("You are paying for more workers than the rush needs.")
    return out


def badness(st: Dict[str, Any], env: Dict[str, Any]) -> float:
    return st["max_age"] + 40 * st["dups"] + 3 * st["legit_left"] + 0.6 * st["workers"] + 2 * st["blocked"]
