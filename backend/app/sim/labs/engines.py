"""Storage engine lab: a B-tree updates pages in place, an LSM-tree appends and merges. Pick the right one for the workload."""
from __future__ import annotations

from typing import Any, Dict, List

from .common import mulberry32, rng, sel, tog

KIND = "engines"
OPS = 600
LEVELS: List[Dict[str, Any]] = [
    {"name": "Write-heavy", "title": "Logging millions of events", "write": 0.9, "range": 0.0, "durable": True, "seed": 1,
     "brief": "Nine in ten operations are writes, as in a log or a metrics store. Each write must survive a crash.", "goal": "Handle the writes cheaply without losing any."},
    {"name": "Read-heavy", "title": "A product catalogue", "write": 0.05, "range": 0.4, "durable": True, "seed": 2,
     "brief": "Almost all operations are reads, some of them range scans. Writes are rare.", "goal": "Keep reads cheap, including range scans."},
    {"name": "Mixed with scans", "title": "An order system", "write": 0.5, "range": 0.2, "durable": True, "seed": 3,
     "brief": "Half writes, half reads, and a fifth of the reads are range scans. Disk space is limited.", "goal": "Balance writes, reads and disk use."},
]


def controls(level: int) -> List[Dict[str, Any]]:
    return [sel("engine", "Storage engine", [["btree", "B-tree (update pages in place)"], ["lsm", "LSM-tree (append, then merge)"]], "lsm", "How data is laid out on disk."),
            rng("memtable", "Memory buffer (LSM)", 1, 16, 1, 2, "Writes collect in memory, then flush as one sorted file. Bigger means fewer files.", " MB"),
            tog("bloom", "Bloom filters (LSM)", False, "A small structure per file that says 'definitely not here', so reads skip files."),
            sel("compaction", "Compaction (LSM)", [["none", "Never merge files"], ["tiered", "Size-tiered (merge similar files)"], ["leveled", "Leveled (keep data in sorted levels)"]], "none", "How background merging works."),
            tog("fsync", "Wait for the disk on each commit (fsync)", True, "Off is faster but a crash can lose acknowledged writes.")]


def public_env(level: int) -> Dict[str, Any]:
    e = LEVELS[level]
    return {"ops": OPS, "write": e["write"], "range": e["range"]}


def run(env: Dict[str, Any], s: Dict[str, Any]) -> Dict[str, Any]:
    rg = mulberry32(env["seed"])
    write_cost = read_cost = disk_writes = 0.0
    files = 4 if s["engine"] == "lsm" else 0            # an existing dataset already lives in several sorted files
    mem = 0.0
    unmerged = 0
    frames: List[Dict[str, Any]] = []
    reads = writes = 0
    for t in range(OPS):
        is_write = rg() < env["write"]
        ev = ""
        page = int(rg() * 8)
        if is_write:
            writes += 1
            if s["engine"] == "btree":
                cost = 8.0 + (3.0 if s["fsync"] else 0.0)               # random page write plus the log
                disk_writes += 2
            else:
                cost = 1.0 + (3.0 if s["fsync"] else 0.0)               # an append to the log, and a memory insert
                mem += 0.02
                disk_writes += 1
                if mem >= s["memtable"] * 0.02 * 50:
                    mem = 0.0
                    files += 1
                    unmerged += 1
                    cost += 6.0                                          # flush a sorted file
                    disk_writes += 8
                    ev = "flush"
                    if s["compaction"] != "none" and unmerged >= (4 if s["compaction"] == "tiered" else 2):
                        files = max(1, files - unmerged + 1)
                        disk_writes += 40 * (1.0 if s["compaction"] == "tiered" else 1.8)
                        cost += 14.0
                        unmerged = 0
                        ev = "compact"
            write_cost += cost
        else:
            reads += 1
            is_range = rg() < env["range"] / max(0.0001, 1 - env["write"]) if env["write"] < 1 else False
            if s["engine"] == "btree":
                cost = 3.0 + (1.0 if is_range else 0.0)           # a few pages down the tree, and a range scan just walks the leaves
            else:
                look = 1 + files
                if s["bloom"]:
                    look = 2 + files * 0.15
                cost = 1.0 * look + (files * 3.0 if is_range else 0.0)    # a range scan has to merge results from every file
            read_cost += cost
        frames.append({"t": t, "op": "w" if is_write else "r", "page": page, "ev": ev, "mem": round(min(1.0, mem / max(0.01, s["memtable"] * 0.02 * 50)), 2), "files": files,
                       "write_cost": round(write_cost), "read_cost": round(read_cost), "disk_writes": round(disk_writes)})
    space = 1.0 + (0.05 * files if s["compaction"] == "none" else 0.0) + (0.6 if s["compaction"] == "tiered" else 0.0) + (0.1 if s["compaction"] == "leveled" else 0.0)
    if s["engine"] == "btree":
        space = 1.3
    lost = (not s["fsync"]) * (1 if env["write"] > 0 else 0)
    stats = {"avg_write": round(write_cost / max(1, writes), 2), "avg_read": round(read_cost / max(1, reads), 2), "total": round(write_cost + read_cost), "files": files,
             "write_amp": round(disk_writes / max(1, writes), 2), "space": round(space, 2), "lost": int(lost), "reads": reads, "writes": writes}
    return {"frames": frames, "stats": stats, "insights": insights(env, s, stats)}


def insights(env: Dict[str, Any], s: Dict[str, Any], st: Dict[str, Any]) -> List[str]:
    out = [f"Average cost per write was {st['avg_write']} and per read {st['avg_read']}. {st['files']} files were left on disk."]
    if s["engine"] == "lsm" and st["files"] > 6 and s["compaction"] == "none":
        out.append("Files pile up because nothing merges them, so every read has to check more and more of them.")
    if s["engine"] == "lsm" and not s["bloom"] and st["files"] > 3:
        out.append("Without Bloom filters, a read for a missing key opens every file. A filter lets it skip nearly all of them.")
    if s["engine"] == "btree" and env["write"] > 0.7:
        out.append("A B-tree writes every change to a random page on disk, which is slow when writes dominate. An LSM-tree turns them into sequential appends.")
    if s["engine"] == "lsm" and env["write"] < 0.2:
        out.append("For read-heavy work an LSM-tree makes reads look in several places. A B-tree reads one tree path.")
    if s["compaction"] != "none":
        out.append(f"Merging files costs extra writing in the background (write amplification {st['write_amp']}x), in return for fewer files to read.")
    if not s["fsync"]:
        out.append("Skipping fsync is faster, but a crash can lose writes you already told the client succeeded.")
    return out


def badness(st: Dict[str, Any], env: Dict[str, Any]) -> float:
    return st["total"] / 60.0 + 40 * st["lost"] + 4 * max(0.0, st["space"] - 1.5)
