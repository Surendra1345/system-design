"""Consensus lab: five nodes elect a leader with votes and terms (Raft-style). Crashes, timeouts and a network partition test it."""
from __future__ import annotations

from typing import Any, Dict, List

from .common import mulberry32, rng, sel, tog

KIND = "consensus"
N = 5
LEVELS: List[Dict[str, Any]] = [
    {"name": "Cold start", "title": "Five nodes start with no leader", "seed": 2, "ticks": 60, "crash": None, "partition": None,
     "brief": "Five nodes boot at the same moment. Each waits for a leader's heartbeat, and if none comes it asks the others for votes. A node needs a majority of the votes to lead.", "goal": "Get a stable leader quickly and keep it."},
    {"name": "Leader crash", "title": "The leader dies at tick 20", "seed": 4, "ticks": 70, "crash": [20, 50], "partition": None,
     "brief": "At tick 20 the leader crashes and stays down for 30 ticks. The others must notice and elect a new one, but not so jumpily that they depose a healthy leader.", "goal": "Spend as little time as possible with no leader."},
    {"name": "Split network", "title": "The network splits into 2 and 3", "seed": 6, "ticks": 80, "crash": None, "partition": [20, 55],
     "brief": "From tick 20 to 55 the leader and one other node cannot talk to the other three. If both sides think they can lead, two leaders accept different writes.", "goal": "Never allow two leaders to commit writes at the same time."},
]


def controls(level: int) -> List[Dict[str, Any]]:
    return [rng("etmin", "Shortest election timeout", 2, 20, 1, 3, "How long a node waits for a heartbeat before it starts an election.", " ticks"),
            rng("etmax", "Longest election timeout", 2, 30, 1, 3, "Each node picks a time between the shortest and the longest.", " ticks"),
            tog("randomize", "Pick the timeout at random", False, "Different timeouts make nodes start elections at different moments."),
            rng("hb", "Heartbeat every", 1, 10, 1, 4, "How often the leader says it is alive.", " ticks"),
            sel("quorum", "Votes needed to lead", [["majority", "A majority (3 of 5)"], ["two", "Any 2 (faster, risky)"]], "majority", "The number of agreeing nodes a leader needs.")]


def public_env(level: int) -> Dict[str, Any]:
    e = LEVELS[level]
    return {"n": N, "ticks": e["ticks"], "crash": e["crash"], "partition": e["partition"]}


def run(env: Dict[str, Any], s: Dict[str, Any]) -> Dict[str, Any]:
    rg = mulberry32(env["seed"])
    need = 3 if s["quorum"] == "majority" else 2
    emin, emax = s["etmin"], max(s["etmax"], s["etmin"])

    def timeout() -> int:
        return emin + int(rg() * (emax - emin + 1)) if s["randomize"] else emin

    role = ["F"] * N
    term = [0] * N
    voted: List[Any] = [None] * N
    votes = [0] * N
    timer = [timeout() for _ in range(N)]
    alive = [True] * N
    group = [0] * N
    hb_in = [0] * N
    msgs: Dict[int, List[Any]] = {}
    no_leader = conflict = elections = 0
    dead_node = 0
    cand_terms: set = set()
    led_terms: set = set()
    frames: List[Dict[str, Any]] = []

    def send(t: int, kind: str, a: int, b: int, tm: int) -> None:
        if alive[a] and alive[b] and group[a] == group[b]:
            msgs.setdefault(t + 1, []).append((kind, a, b, tm))

    for t in range(env["ticks"]):
        if env["crash"]:
            c0, c1 = env["crash"]
            if t == c0:
                leaders = [i for i in range(N) if role[i] == "L" and alive[i]]
                dead = leaders[0] if leaders else 0
                dead_node = dead
                alive[dead] = False
            if t == c1:
                alive[dead_node] = True
                role[dead_node] = "F"
                timer[dead_node] = timeout()
        if env["partition"]:
            p0, p1 = env["partition"]
            if t == p0:
                leaders = [i for i in range(N) if role[i] == "L"]
                a = leaders[0] if leaders else 0
                side = {a, (a + 1) % N}
                group = [1 if i in side else 0 for i in range(N)]
            if t == p1:
                group = [0] * N
        shown = []
        for kind, a, b, tm in msgs.pop(t, []):
            if not (alive[a] and alive[b]) or group[a] != group[b]:
                continue
            shown.append([kind, a, b])
            if tm > term[b]:
                term[b], role[b], voted[b] = tm, "F", None
            if kind == "rv" and tm == term[b] and voted[b] in (None, a):
                voted[b] = a
                timer[b] = timeout()
                send(t, "vote", b, a, tm)
            elif kind == "vote" and role[b] == "C" and tm == term[b]:
                votes[b] += 1
                if votes[b] >= need:
                    role[b] = "L"
                    led_terms.add(tm)
                    hb_in[b] = 0
            elif kind == "hb" and tm >= term[b]:
                term[b], role[b] = tm, "F"
                timer[b] = timeout()
        for i in range(N):
            if not alive[i]:
                continue
            if role[i] == "L":
                if hb_in[i] <= 0:
                    for j in range(N):
                        if j != i:
                            send(t, "hb", i, j, term[i])
                    hb_in[i] = s["hb"]
                hb_in[i] -= 1
            else:
                timer[i] -= 1
                if timer[i] <= 0:
                    role[i], term[i], voted[i], votes[i] = "C", term[i] + 1, i, 1
                    cand_terms.add(term[i])
                    elections += 1
                    timer[i] = timeout()
                    for j in range(N):
                        if j != i:
                            send(t, "rv", i, j, term[i])
        usable = []
        for i in range(N):
            if alive[i] and role[i] == "L":
                reach = sum(1 for j in range(N) if alive[j] and group[j] == group[i])
                if reach >= need:
                    usable.append(i)
        if not usable:
            no_leader += 1
        if len(usable) > 1:
            conflict += 1
        frames.append({"t": t, "nodes": [{"role": role[i], "term": term[i], "alive": alive[i], "group": group[i], "timer": timer[i]} for i in range(N)], "msgs": shown[:14],
                       "leaders": usable, "no_leader": no_leader, "conflict": conflict})
    split = len(cand_terms - led_terms)
    stats = {"no_leader": no_leader, "conflict": conflict, "elections": elections, "split_votes": split, "ticks": env["ticks"]}
    return {"frames": frames, "stats": stats, "insights": insights(env, s, stats)}


def insights(env: Dict[str, Any], s: Dict[str, Any], st: Dict[str, Any]) -> List[str]:
    out = [f"The cluster had no usable leader for {st['no_leader']} of {st['ticks']} ticks. There were {st['elections']} elections and {st['split_votes']} of them failed to elect anyone."]
    if st["split_votes"] > 1 and not s["randomize"]:
        out.append("Every node timed out at the same moment, voted for itself, and nobody got a majority. Random timeouts make one node ask first and win.")
    if s["hb"] >= s["etmin"]:
        out.append("The leader sends heartbeats less often than followers lose patience, so followers keep starting elections against a healthy leader. Heartbeats must be much more frequent than the shortest timeout.")
    if st["conflict"]:
        out.append(f"For {st['conflict']} ticks two leaders could both commit writes, each side believing it was in charge (split brain). Requiring a majority makes that impossible, because two groups cannot both hold 3 of 5.")
    if s["etmin"] > 12:
        out.append("Long timeouts mean a real crash goes unnoticed for a long time.")
    return out


def badness(st: Dict[str, Any], env: Dict[str, Any]) -> float:
    return st["no_leader"] + 15 * st["conflict"] + 0.5 * st["elections"]
