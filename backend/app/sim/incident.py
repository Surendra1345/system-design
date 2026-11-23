"""
Incident simulator.

A production system is broken. The player investigates with terminal-style commands and then
types what they would do, in their own words. Every move costs a minute while errors keep rising.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Tuple

CLUE_KEYS = ["logs", "metrics", "traces", "deploys", "deps"]
CLUE_ALIASES = {
    "logs": "logs", "log": "logs", "tail": "logs", "journalctl": "logs",
    "metrics": "metrics", "metric": "metrics", "dashboard": "metrics", "graphs": "metrics", "grafana": "metrics",
    "traces": "traces", "trace": "traces", "tracing": "traces", "jaeger": "traces",
    "deploys": "deploys", "deploy": "deploys", "releases": "deploys", "release": "deploys", "changelog": "deploys", "history": "deploys",
    "deps": "deps", "dependencies": "deps", "dependency": "deps", "upstream": "deps", "status": "deps",
}


FILLER = {"check", "show", "see", "look", "at", "the", "view", "open", "run", "get", "list", "my", "me", "a", "tail", "cat", "please", "now", "first", "some", "recent", "latest", "all", "us"}


class Incident:
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.err = float(data.get("start", 60))
        self.tick = 0
        self.resolved = False
        self.failed = False
        self.applied: List[str] = []
        self.seen: List[str] = []
        self.pain = 0.0
        self.relapse = 0
        self.fixing = False
        self.history: List[float] = [self.err]
        self.rise = float(data.get("rise", 6))
        self.max = int(data.get("max", 12))

    @property
    def over(self) -> bool:
        return self.resolved or self.failed

    def _pass(self) -> None:
        self.pain += self.err
        self.tick += 1
        if not self.resolved:
            if self.fixing:
                self.err = max(0.0, self.err - 35)
                if self.err <= 5:
                    self.resolved, self.err = True, 0.0
            elif self.relapse > 0:
                self.relapse -= 1
            else:
                self.err = min(100.0, self.err + self.rise)
        if self.tick >= self.max and not self.resolved:
            self.failed = True
        self.history.append(self.err)

    def investigate(self, key: str) -> Dict[str, Any]:
        if self.over or key not in self.data["clues"]:
            return {"ok": False}
        if key not in self.seen:
            self.seen.append(key)
        self._pass()
        return {"ok": True, "text": self.data["clues"][key]}

    def act(self, act_id: str) -> Dict[str, Any]:
        act = next((a for a in self.data["acts"] if a[0] == act_id), None)
        if self.over or act is None:
            return {"ok": False}
        kind = act[1]
        if kind == "fix":
            if act_id not in self.applied:
                self.applied.append(act_id)
            if all(n in self.applied for n in self.data["need"]):
                self.fixing = True
                msg = "That is the root cause. Errors fall back to normal."
            else:
                msg = "Good move, but one more fix is needed."
        elif kind == "band":
            self.err = max(0.0, self.err - 30)
            self.relapse = 2
            msg = act[3] if len(act) > 3 else "That helps for a moment, but the cause is still there."
        else:
            self.err = min(100.0, self.err + 8)
            msg = act[3] if len(act) > 3 else "That did not help and cost time."
        self._pass()
        while self.fixing and not self.over:
            self._pass()  # recovery plays out on its own
        return {"ok": True, "kind": kind, "msg": msg, "label": act[2]}

    def result(self) -> Dict[str, Any]:
        stars = 0
        if self.resolved:
            par = self.data["par"]
            stars = 3 if self.tick <= par else 2 if self.tick <= par + 3 else 1
            if stars == 3 and not self.seen:
                stars = 2  # a lucky guess without evidence cannot earn the top rating
        return {"resolved": self.resolved, "minutes": self.tick, "stars": stars, "pain": self.pain}

    def public_state(self) -> Dict[str, Any]:
        return {"minute": self.tick, "max": self.max, "error_rate": round(self.err), "history": [round(h) for h in self.history],
                "resolved": self.resolved, "failed": self.failed, "seen": self.seen}


def replay(data: Dict[str, Any], events: List[Dict[str, Any]]) -> Incident:
    inc = Incident(data)
    for e in (events or [])[:60]:
        if inc.over:
            break
        if e.get("k") == "inv":
            inc.investigate(str(e.get("id")))
        elif e.get("k") == "act":
            inc.act(str(e.get("id")))
    return inc


# ---------------------------------------------------------------- understanding what the player typed
STOP = set("the a an to of and or in on for with it we i you my our is are be this that then so please just now at by as from "
           "up down out can should would will let lets us do did does make made want need try how what when".split())


def _stem(w: str) -> str:
    for suf in ("ing", "ed", "es", "s", "e"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _tokens(text: str) -> List[str]:
    return [_stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP]


def _idf(acts: List[List[str]]) -> Dict[str, float]:
    """Words that appear in few actions are more telling than words that appear in many."""
    df: Dict[str, int] = {}
    for a in acts:
        for t in set(_tokens(a[2])):
            df[t] = df.get(t, 0) + 1
    n = len(acts)
    return {t: math.log(1 + n / c) for t, c in df.items()}


def parse_command(inc: Incident, text: str) -> Tuple[str, Optional[str], Optional[str]]:
    """Returns (kind, id, note). kind is help | inv | act | unknown."""
    raw = text.strip()
    if not raw:
        return "unknown", None, "Type a command or describe what you would do."
    first = re.findall(r"[a-z]+", raw.lower())[:1]
    if first and first[0] in ("help", "?", "h"):
        return "help", None, None
    words = raw.lower().split()
    if len(words) <= 3 and all(re.sub(r"[^a-z]", "", w) in CLUE_ALIASES or re.sub(r"[^a-z]", "", w) in FILLER for w in words):
        for w in words:
            key = CLUE_ALIASES.get(re.sub(r"[^a-z]", "", w))
            if key:
                return "inv", key, None
    it = set(_tokens(raw))
    if not it:
        return "unknown", None, "I did not catch that. Describe an action, for example 'roll back the last deploy'."
    exact = [a[0] for a in inc.data["acts"] if set(_tokens(a[2])) == it]
    if len(exact) == 1:  # the player typed an action exactly as written
        return "act", exact[0], None
    idf = _idf(inc.data["acts"])
    scored: List[Tuple[float, str]] = []
    for a in inc.data["acts"]:
        lt = set(_tokens(a[2]))
        total = sum(idf[t] for t in lt)
        hit = sum(idf[t] for t in lt & it)
        scored.append((hit / total if total else 0.0, a[0]))
    scored.sort(reverse=True)
    if scored and scored[0][0] >= 0.35 and (len(scored) < 2 or scored[0][0] - scored[1][0] >= 0.10):
        return "act", scored[0][1], None
    # a short but precise phrase such as "add timeouts": every word the player used belongs to one action
    if len(it) >= 2 and scored:
        best = next(a for a in inc.data["acts"] if a[0] == scored[0][1])
        lt = set(_tokens(best[2]))
        if it <= lt and scored[0][0] >= 0.07 and (len(scored) < 2 or scored[0][0] - scored[1][0] >= 0.03):
            return "act", scored[0][1], None
    if len(words) <= 8:  # "show me the dashboard", "check the deploy history"
        for w in words:
            key = CLUE_ALIASES.get(re.sub(r"[^a-z]", "", w))
            if key:
                return "inv", key, None
    return "unknown", None, None  # caller may ask the language model, or ask the player to rephrase
