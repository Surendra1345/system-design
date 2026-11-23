"""Summarises pilot feedback: which pages learners found unclear, the bugs they hit, and what they asked for.
Run from backend/:  python -m tools.pilot_report"""
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import Feedback  # noqa: E402


def build(rows):
    pages = defaultdict(Counter)
    for r in rows:
        pages[r.page][r.kind] += 1
    ranked = []
    for page, c in pages.items():
        clear, unclear = c["clear"], c["unclear"] + c["confusing"]
        total = clear + unclear
        ranked.append((page, clear, unclear, (unclear / total) if total else 0.0, c["bug"]))
    ranked.sort(key=lambda x: (-x[3], -x[2]))
    return ranked


def main():
    with SessionLocal() as db:
        rows = db.scalars(select(Feedback).order_by(Feedback.at)).all()
    if not rows:
        print("No feedback yet.")
        return
    ratings = [r.rating for r in rows if r.rating]
    print("Notes: %d   Testers (signed in): %d   Average rating: %s\n" % (
        len(rows), len({r.user_id for r in rows if r.user_id}), "%.1f" % (sum(ratings) / len(ratings)) if ratings else "n/a"))
    print("Pages to fix first (share of 'not clear' answers):")
    for page, clear, unclear, share, bugs in build(rows)[:15]:
        if unclear or bugs:
            print("  %-28s clear %-3d not clear %-3d (%3.0f%%)  bugs %d" % (page, clear, unclear, share * 100, bugs))
    for kind, title in (("bug", "Bugs"), ("confusing", "Confusing"), ("idea", "Ideas")):
        items = [r for r in rows if r.kind == kind and r.message]
        if items:
            print("\n%s:" % title)
            for r in items:
                print("  [%s] %s" % (r.page, r.message.replace("\n", " ")))


if __name__ == "__main__":
    main()
