"""Find the best settings for every lab level and write star thresholds.

Run from the backend folder:  python -m tools.calibrate_labs
Stars are relative to the gap between the default settings (0 stars) and the best settings found (3 stars).
"""
from __future__ import annotations

import itertools
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.sim import labs  # noqa: E402
from app.sim.labs.common import clean_settings  # noqa: E402

OUT = labs.THRESHOLDS_FILE


def values(c):
    if c["type"] == "select":
        return [o[0] for o in c["options"]]
    if c["type"] == "toggle":
        return [False, True]
    if c["type"] == "range":
        n = int(round((c["max"] - c["min"]) / c["step"]))
        return [c["min"] + i * c["step"] for i in range(n + 1)]
    return None


def sample(controls, rg):
    s = {}
    for c in controls:
        if c["type"] == "multi":
            k = rg.randint(0, c["max"])
            s[c["id"]] = rg.sample([o[0] for o in c["options"]], k)
        else:
            s[c["id"]] = rg.choice(values(c))
    return s


def score(m, env, level, s):
    s = clean_settings(m.controls(level), s)
    return m.badness(m.run(env, s)["stats"], env), s


def search(lesson, level):
    m = labs.module(lesson)
    env = m.LEVELS[level]
    controls = m.controls(level)
    rg = random.Random(7)
    best, bs = None, 1e18
    for _ in range(4000):
        b, s = score(m, env, level, sample(controls, rg))
        if b < bs:
            best, bs = s, b
    improved = True
    while improved:                                   # coordinate descent
        improved = False
        for c in controls:
            if c["type"] == "multi":
                opts = [o[0] for o in c["options"]]
                for o in opts:
                    cand = dict(best)
                    cur = list(cand[c["id"]])
                    cand[c["id"]] = [x for x in cur if x != o] if o in cur else (cur + [o])[: c["max"]]
                    b, s = score(m, env, level, cand)
                    if b < bs - 1e-9:
                        best, bs, improved = s, b, True
            else:
                for v in values(c):
                    cand = dict(best)
                    cand[c["id"]] = v
                    b, s = score(m, env, level, cand)
                    if b < bs - 1e-9:
                        best, bs, improved = s, b, True
    default, _ = score(m, env, level, {})
    return best, bs, default


def thresholds(b, d):
    """3 stars: close to the best result found. 2 and 1 stars are looser. The default settings must always earn 0 stars."""
    gap = d - b
    t3 = min(b * 1.25 + 2, b + 0.15 * gap)
    t2 = max(min(b * 1.8 + 6, b + 0.4 * gap), t3 + 0.01)
    t1 = max(min(b * 3 + 12, b + 0.6 * gap), t2 + 0.01)
    return [round(t3, 2), round(t2, 2), round(t1, 2)]


def main():
    only = sys.argv[1:]
    res = json.loads(OUT.read_text()) if only and OUT.exists() else {}
    for lesson in labs.LESSON_LAB:
        if only and lesson not in only:
            continue
        for level in range(labs.n_levels(lesson)):
            best, b, d = search(lesson, level)
            t = thresholds(b, d)
            res["%s:%d" % (lesson, level)] = {"solution": best, "best": round(b, 2), "default": round(d, 2), "stars": t}
            print("%-12s L%d best=%7.2f default=%7.2f stars<=%s" % (lesson, level, b, d, t), flush=True)
    OUT.write_text(json.dumps(res, indent=1, sort_keys=True))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
