"""SLO lab: turn 'reliable' into a number, spend an error budget, and page people only when it matters."""
from __future__ import annotations

from typing import Any, Dict, List

from .common import rng, sel, tog

KIND = "slo"
MONTH = 30 * 24 * 60
LEVELS: List[Dict[str, Any]] = [
    {"name": "A quiet month", "title": "Set a target and an alert rule", "needs": 99.9, "incidents": [[2, 0, 12, 100], [9, 0, 40, 15], [17, 0, 180, 5], [24, 0, 300, 2]],
     "brief": "Four incidents hit your service this month. Users notice anything below 99.9% availability. A paged person fixes a problem within minutes, and an unnoticed one runs its full length. Pick an SLO and an alert rule.", "goal": "Stay above 99.9% without waking people for blips."},
    {"name": "Noisy month", "title": "Too many small blips, and one slow burn", "needs": 99.9, "incidents": [[1, 0, 8, 100], [3, 0, 60, 2], [5, 0, 30, 3], [8, 0, 100, 2], [11, 0, 50, 4], [14, 0, 720, 1], [19, 0, 20, 5], [23, 0, 90, 2], [27, 0, 40, 3]],
     "brief": "Nine incidents: a sudden outage, a long slow burn that never looks dramatic, and a lot of tiny blips. A rule that pages on every blip exhausts on-call, while a rule that only watches fast burns misses the slow one.", "goal": "Catch both serious incidents and ignore the blips."},
    {"name": "Strict customer", "title": "A contract with a refund", "needs": 99.95, "incidents": [[4, 0, 6, 100], [10, 0, 30, 10], [16, 0, 120, 5], [21, 0, 40, 6], [26, 0, 60, 8]],
     "brief": "A customer's contract refunds them below 99.95%. Your internal SLO must be stricter than the promise to leave a safety margin, but not so strict that you can never ship.", "goal": "Keep a safety margin without freezing releases all month."},
]
NINES = {"99": 0.01, "99.5": 0.005, "99.9": 0.001, "99.95": 0.0005, "99.99": 0.0001}


def controls(level: int) -> List[Dict[str, Any]]:
    return [sel("slo", "Your SLO", [["99", "99%"], ["99.5", "99.5%"], ["99.9", "99.9%"], ["99.95", "99.95%"], ["99.99", "99.99%"]], "99", "The target for the share of requests that succeed."),
            sel("alert", "When to page a human", [["any", "On every error spike"], ["burn", "When the budget burns fast (14.4x)"], ["slow", "When a slow burn would spend 10% of the budget"]], "any", "The alert rule."),
            tog("freeze", "Freeze releases when the budget is spent", False, "Reliability work takes priority until the next month.")]


def public_env(level: int) -> Dict[str, Any]:
    e = LEVELS[level]
    return {"needs": e["needs"], "incidents": [{"day": i[0], "len": i[2], "err": i[3]} for i in e["incidents"]], "month": MONTH}


def run(env: Dict[str, Any], s: Dict[str, Any]) -> Dict[str, Any]:
    allowed = NINES[s["slo"]]
    budget_total = MONTH * allowed                     # minutes of full outage the SLO allows
    spent = 0.0
    pages = false_pages = missed = 0
    frames: List[Dict[str, Any]] = []
    frozen_days = 0
    for idx, (day, start_min, length, err) in enumerate(env["incidents"]):
        full_cost = length * err / 100.0               # full-outage minutes if nobody reacts
        burn = (err / 100.0) / allowed                 # how many times faster than allowed the budget burned
        big = full_cost >= 0.10 * budget_total
        if s["alert"] == "any":
            paged = err >= 1
        elif s["alert"] == "burn":
            paged = burn >= 14.4 and length >= 5 and full_cost >= 0.05 * budget_total
        else:
            paged = full_cost >= 0.10 * budget_total
        # a paged engineer mitigates quickly; an unnoticed incident runs its whole length
        mitigated = min(length, 6) if s["alert"] != "slow" else min(length, max(6, int(length * 0.25)))
        cost = (mitigated if paged else length) * err / 100.0
        spent += cost
        if paged:
            pages += 1
            if not big:
                false_pages += 1
        elif big:
            missed += 1
        frames.append({"t": idx, "day": day, "len": length, "err": err, "cost": round(cost, 2), "spent": round(spent, 2), "budget": round(budget_total, 2), "paged": paged, "burn": round(burn, 1)})
        if s["freeze"] and spent > budget_total and frozen_days == 0:
            frozen_days = 30 - day
    avail = 100 * (1 - spent / MONTH)
    breached = avail < env["needs"]
    stats = {"availability": round(avail, 3), "spent": round(spent, 1), "budget": round(budget_total, 1), "pages": pages, "false_pages": false_pages, "missed": missed, "breached": breached,
             "frozen_days": frozen_days, "slo_gap": round(float(s["slo"]) - env["needs"], 2)}
    return {"frames": frames, "stats": stats, "insights": insights(env, s, stats)}


def insights(env: Dict[str, Any], s: Dict[str, Any], st: Dict[str, Any]) -> List[str]:
    out = [f"Availability for the month was {st['availability']}%. You spent {st['spent']} of the {st['budget']} minutes of budget your SLO allowed."]
    out.append(f"{st['pages']} pages went out, {st['false_pages']} of them for small incidents, and {st['missed']} serious incident(s) were missed.")
    if st["false_pages"] > 2:
        out.append("Paging on every spike wakes people for blips that barely touch the budget. Alert on how fast the budget is burning instead.")
    if st["missed"]:
        out.append("A rule that only watches fast burns can miss a long, slow failure. A slow-burn rule catches those.")
    if st["breached"]:
        out.append(f"Real availability fell below the {env['needs']}% that users need.")
    if st["slo_gap"] < 0:
        out.append("Your SLO is looser than what users need, so you would not notice trouble until it is too late.")
    if st["slo_gap"] > 0.05:
        out.append("Each extra nine costs far more than the last. Setting the SLO much stricter than users need only freezes your releases.")
    if st["frozen_days"]:
        out.append(f"The budget was spent, so releases were frozen for {st['frozen_days']} days.")
    return out


def badness(st: Dict[str, Any], env: Dict[str, Any]) -> float:
    return 4 * st["false_pages"] + 20 * st["missed"] + (30 if st["breached"] else 0) + 40 * max(0.0, -st["slo_gap"]) + 25 * max(0.0, st["slo_gap"] - 0.05) + 0.4 * st["frozen_days"]
