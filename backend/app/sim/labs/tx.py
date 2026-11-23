"""Transactions lab: concurrent transactions over a tiny database with real locks, snapshots and deadlock detection."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .common import mulberry32, sel, tog

KIND = "tx"
MAXT = 300


def _inc(acct: str):
    return [("r", acct, "x"), ("w", acct, lambda r: r["x"] + 1), ("c",)]


def _xfer(a: str, b: str, amt: int):
    return [("r", a, "x"), ("r", b, "y"), ("w", a, lambda r, amt=amt: r["x"] - amt), ("w", b, lambda r, amt=amt: r["y"] + amt), ("c",)]


def _audit(accts: List[str]):
    return [("r", a, a) for a in accts] + [("c",)]


LEVELS: List[Dict[str, Any]] = [
    {"name": "Lost update", "title": "Ten people click Like at the same time", "seed": 3, "start": {"C": 0}, "total": None, "expect": {"C": 10},
     "txns": [(i, _inc("C")) for i in range(10)],
     "brief": "Ten transactions each read a counter, add one and write it back. If they interleave, two of them read the same number and one increase vanishes.", "goal": "The counter must end at 10, as fast as possible."},
    {"name": "The auditor", "title": "Moving money while someone adds it up", "seed": 5, "start": {"A": 100, "B": 100, "C": 100}, "total": 300, "expect": None,
     "txns": [(0, _xfer("A", "B", 30)), (1, _xfer("B", "C", 20)), (2, _xfer("C", "A", 10)), (3, _xfer("A", "C", 25)), (4, _audit(["A", "B", "C"])), (6, _audit(["A", "B", "C"])), (8, _audit(["C", "B", "A"]))],
     "brief": "Four transfers move money around three accounts while the auditor adds up all three balances, three times. The total must always be 300.", "goal": "Every audit must see exactly 300, and every transfer must finish."},
    {"name": "Deadlock", "title": "Two transfers that need each other's accounts", "seed": 7, "start": {"A": 100, "B": 100, "C": 100}, "total": 300, "expect": None,
     "txns": [(0, _xfer("A", "B", 10)), (0, _xfer("B", "A", 20)), (1, _xfer("B", "C", 10)), (1, _xfer("C", "B", 5)), (2, _xfer("A", "C", 5)), (2, _xfer("C", "A", 5))],
     "brief": "Six transfers go in opposite directions between the same accounts. When each one holds a lock the other needs, they wait forever until the database picks a victim.", "goal": "Finish all transfers with as few aborts and as little waiting as possible."},
]


def controls(level: int) -> List[Dict[str, Any]]:
    return [sel("isolation", "Isolation level", [["ru", "Read uncommitted"], ["rc", "Read committed"], ["rr", "Repeatable read (snapshot)"], ["ser", "Serializable (locks)"]], "rc", "How much one transaction can see of the others."),
            tog("for_update", "Lock rows when reading (SELECT ... FOR UPDATE)", False, "Reading a row takes a lock on it, so nobody changes it before you write."),
            tog("ordered", "Always lock accounts in alphabetical order", False, "A simple rule that stops two transactions waiting on each other.")]


def public_env(level: int) -> Dict[str, Any]:
    e = LEVELS[level]
    return {"accounts": list(e["start"].keys()), "start": e["start"], "n": len(e["txns"]), "total": e["total"], "expect": e["expect"]}


class T:
    def __init__(self, tid: int, start: int, prog: List[Any]):
        self.id, self.start, self.prog = tid, start, prog
        self.reset(0)

    def reset(self, begin: int) -> None:
        self.pc, self.regs, self.writes, self.locks, self.snap, self.snap_ver = 0, {}, {}, {}, None, {}
        self.state, self.wait, self.resume = "ready", None, 0
        self.lockq, self.prelocked = [], False


def run(env: Dict[str, Any], s: Dict[str, Any]) -> Dict[str, Any]:
    rg = mulberry32(env["seed"])
    db = dict(env["start"])
    ver = {k: 0 for k in db}
    dirty: Dict[str, Any] = {}
    txns = [T(i, st, prog) for i, (st, prog) in enumerate(env["txns"])]
    held: Dict[str, Dict[int, str]] = {k: {} for k in db}
    aborts = deadlocks = bad_audits = waits = 0
    frames: List[Dict[str, Any]] = []
    iso = s["isolation"]

    def acquire(tx: T, acct: str, mode: str) -> Optional[int]:
        h = held[acct]
        others = {i: m for i, m in h.items() if i != tx.id}
        if mode == "S" and all(m == "S" for m in others.values()):
            h.setdefault(tx.id, "S"); tx.locks[acct] = h[tx.id]; return None
        if mode == "X" and not others:
            h[tx.id] = "X"; tx.locks[acct] = "X"; return None
        if mode == "S" and tx.id in h:
            return None
        return next(iter(others))

    def release(tx: T) -> None:
        for a in list(tx.locks):
            held[a].pop(tx.id, None)
        tx.locks = {}
        for a in list(dirty):
            if dirty[a][0] == tx.id:
                del dirty[a]

    def abort(tx: T, t: int, why: str) -> None:
        nonlocal aborts
        aborts += 1
        release(tx)
        tx.reset(t)
        tx.state, tx.resume = "aborted", t + 1 + int(rg() * 6)
        events.append(f"T{tx.id + 1} aborted ({why}) and will retry")

    def read_value(tx: T, a: str) -> int:
        if a in tx.writes:
            return tx.writes[a]
        if iso == "ru" and a in dirty:
            return dirty[a][1]
        if iso in ("rr",):
            if tx.snap is None:
                tx.snap, tx.snap_ver = dict(db), dict(ver)
            return tx.snap[a]
        return db[a]

    t = 0
    while t < MAXT and any(x.state != "done" for x in txns):
        events: List[str] = []
        cand = [x for x in txns if x.state != "done" and x.start <= t and x.resume <= t]
        for x in cand:
            if x.state == "aborted":
                x.state = "ready"
        progressed = False
        tried = set()
        while True:
            pool = [x for x in cand if x.id not in tried and x.state in ("ready", "blocked")]
            if not pool:
                break
            tx = pool[int(rg() * len(pool))]
            tried.add(tx.id)
            op = tx.prog[tx.pc]
            blocker: Optional[int] = None
            if s["ordered"] and tx.pc == 0 and not tx.prelocked and (s["for_update"] or any(o[0] == "w" for o in tx.prog)):
                tx.lockq = sorted({o[1] for o in tx.prog if o[0] in ("r", "w")})
                tx.prelocked = True
            if tx.lockq:
                a = tx.lockq[0]
                blocker = acquire(tx, a, "X")
                if blocker is None:
                    tx.lockq.pop(0)
                    events.append(f"T{tx.id + 1} locks {a}")
                    tx.state, tx.wait = "ready", None
                    progressed = True
                    break
            elif op[0] == "r":
                a = op[1]
                mode = "X" if s["for_update"] else ("S" if iso == "ser" else None)
                if mode:
                    blocker = acquire(tx, a, mode)
                if blocker is None:
                    tx.regs[op[2]] = read_value(tx, a)
                    events.append(f"T{tx.id + 1} reads {a} = {tx.regs[op[2]]}")
            elif op[0] == "w":
                a = op[1]
                blocker = acquire(tx, a, "X")
                if blocker is None:
                    if iso == "rr":
                        if tx.snap is None:
                            tx.snap, tx.snap_ver = dict(db), dict(ver)
                        if ver[a] != tx.snap_ver.get(a, ver[a]):
                            abort(tx, t, "someone changed " + a + " first"); progressed = True; break
                    val = op[2](tx.regs)
                    tx.writes[a] = val
                    if iso == "ru":
                        dirty[a] = (tx.id, val)
                    events.append(f"T{tx.id + 1} writes {a} = {val}")
            else:
                for a, v in tx.writes.items():
                    db[a] = v
                    ver[a] += 1
                if env["total"] is not None and len(tx.prog) and all(o[0] == "r" for o in tx.prog[:-1]):
                    total = sum(tx.regs.values())
                    if total != env["total"]:
                        bad_audits += 1
                        events.append(f"T{tx.id + 1} audit saw {total}, not {env['total']}")
                    else:
                        events.append(f"T{tx.id + 1} audit saw {total}")
                else:
                    events.append(f"T{tx.id + 1} commits")
                release(tx)
                tx.state = "done"
                progressed = True
                break
            if blocker is not None:
                tx.state, tx.wait = "blocked", blocker
                events.append(f"T{tx.id + 1} waits for T{blocker + 1}")
                waits += 1
                continue
            tx.pc += 1
            tx.state, tx.wait = "ready", None
            progressed = True
            break
        # deadlock detection: follow the wait-for chain
        blocked = {x.id: x.wait for x in txns if x.state == "blocked"}
        for start in list(blocked):
            seen, cur = [], start
            while cur in blocked and cur not in seen:
                seen.append(cur); cur = blocked[cur]
            if cur in seen:
                cyc = seen[seen.index(cur):]
                victim = max(cyc)
                deadlocks += 1
                events.append("DEADLOCK between " + ", ".join("T%d" % (c + 1) for c in cyc))
                abort(txns[victim], t, "deadlock victim")
                break
        frames.append({"t": t, "state": [x.state for x in txns], "pc": [x.pc for x in txns], "db": dict(db), "events": events[:6], "locks": {a: dict(h) for a, h in held.items() if h}})
        t += 1
    expect = env["expect"]
    lost = sum(abs(expect[k] - db[k]) for k in expect) if expect else 0
    unfinished = sum(1 for x in txns if x.state != "done")
    stats = {"final": dict(db), "lost": lost, "bad_audits": bad_audits, "deadlocks": deadlocks, "aborts": aborts, "waits": waits, "ticks": t, "unfinished": unfinished,
             "total_ok": env["total"] is None or sum(db.values()) == env["total"]}
    return {"frames": frames, "stats": stats, "insights": insights(env, s, stats)}


def insights(env: Dict[str, Any], s: Dict[str, Any], st: Dict[str, Any]) -> List[str]:
    out = [f"It took {st['ticks']} ticks. {st['aborts']} transactions had to retry, there were {st['deadlocks']} deadlocks and {st['bad_audits']} wrong audits."]
    if st["lost"]:
        out.append(f"{st['lost']} updates were lost: two transactions read the same old value and the second write overwrote the first. Lock the row when you read it, or use a stricter isolation level.")
    if st["bad_audits"]:
        out.append("The auditor saw money in the middle of a transfer. A snapshot (repeatable read) gives it one consistent view.")
    if s["isolation"] == "ru" and (st["bad_audits"] or env["total"] is not None):
        out.append("Read uncommitted lets you read changes that may still be rolled back (dirty reads).")
    if st["deadlocks"]:
        out.append("Transactions held one lock and waited for another that someone else held. Taking locks in a fixed order removes the cycle.")
    if s["isolation"] == "ser" and st["deadlocks"] and env["expect"]:
        out.append("Two serializable transactions both took a shared lock and then both wanted to upgrade it, so each waited for the other.")
    if st["unfinished"]:
        out.append(f"{st['unfinished']} transactions never finished.")
    return out


def badness(st: Dict[str, Any], env: Dict[str, Any]) -> float:
    return 25 * st["lost"] + 20 * st["bad_audits"] + 4 * st["deadlocks"] + 2 * st["aborts"] + st["ticks"] / 5 + 30 * st["unfinished"] + (0 if st["total_ok"] else 50)
