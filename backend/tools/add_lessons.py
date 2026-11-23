"""Add the new lessons to the content files. Safe to re-run: it replaces entries with the same id.
Run from the backend folder: python -m tools.add_lessons"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import new_lessons_a as A, new_lessons_b as B  # noqa: E402

C = Path(__file__).resolve().parents[1] / "app" / "content"
ORDER_AFTER = {"search": "shard", "dr": "chaos", "notify": "ecommerce", "geo": "chat"}      # place each new lesson next to related ones


def load(n): return json.loads((C / n).read_text())
def save(n, d): (C / n).write_text(json.dumps(d, indent=1, ensure_ascii=False))


lessons, explain, interviews = load("lessons.json"), load("explain.json"), load("interviews.json")
deep_file = C / "deep" / "deep_F.json"
deep = json.loads(deep_file.read_text()) if deep_file.exists() else {}
for mod in (A, B):
    for lid, l in mod.LESSONS.items():
        lessons["lessons"] = [x for x in lessons["lessons"] if x["id"] != lid]
        idx = next(i for i, x in enumerate(lessons["lessons"]) if x["id"] == ORDER_AFTER[lid]) + 1
        lessons["lessons"].insert(idx, l)
        explain[lid] = mod.EXPLAIN[lid]
        deep[lid] = mod.DEEP[lid]
        interviews[lid] = mod.INTERVIEW[lid]
save("lessons.json", lessons); save("explain.json", explain); save("interviews.json", interviews)
deep_file.write_text(json.dumps(deep, indent=1, ensure_ascii=False))
print("lessons:", len(lessons["lessons"]))
