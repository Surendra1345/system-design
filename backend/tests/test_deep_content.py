"""The researched deep dives must be complete, well-formed and free of schedules or time estimates."""
import json
import re

from app import content

KINDS = {"paper", "book", "docs", "blog", "talk"}
SCHEDULE = re.compile(r"\b(\d+|one|two|three|four|six|eight|twelve)[- ]weeks?\b|\bper week\b|\bhours (a|per) (day|week)\b|\bstudy plan\b|\breading time\b|\bminutes? to read\b", re.I)


def test_every_lesson_has_a_complete_deep_dive():
    deep = content.deep()
    missing = sorted(set(content.lesson_index()) - set(deep))
    assert not missing, "no deep dive for: %s" % missing
    assert set(deep) <= set(content.lesson_index()), "deep dive for an unknown lesson"
    for lid, d in deep.items():
        assert 4 <= len(d["how"]) <= 6, lid
        assert all(x["h"].strip() and len(x["p"]) > 60 for x in d["how"]), lid
        w = d["worked"]
        assert w["title"] and 4 <= len(w["steps"]) <= 8 and w["result"], lid
        c = d["case"]
        assert c["who"] and c["title"] and len(c["text"]) > 120, lid
        assert 2 <= len(d["choose"]) <= 6 and all(len(r) == 3 and all(x.strip() for x in r) for r in d["choose"]), lid   # header row plus options
        assert 4 <= len(d["mistakes"]) <= 6 and all(len(m) > 30 for m in d["mistakes"]), lid
        assert 4 <= len(d["reading"]) <= 8, lid
        assert len({r["kind"] for r in d["reading"]}) >= 3, (lid, "needs at least 3 kinds of source")
        for r in d["reading"]:
            assert r["title"] and r["by"] and r["kind"] in KINDS, (lid, r)


def test_links_are_https_and_not_duplicated_within_a_lesson():
    for lid, d in content.deep().items():
        urls = [r["url"] for r in d["reading"] if r.get("url")]
        if d["case"].get("source", {}).get("url"):
            urls.append(d["case"]["source"]["url"])
        for u in urls:
            assert re.match(r"^https://[^\s]+$", u), (lid, u)
        assert len(set(d_["url"] for d_ in d["reading"] if d_.get("url"))) == len([r for r in d["reading"] if r.get("url")]), lid


def test_no_schedules_or_time_estimates_in_the_deep_dives():
    for lid, d in content.deep().items():
        text = json.dumps(d)
        found = SCHEDULE.search(text)
        assert not found, (lid, found.group(0))
        assert "<" not in re.sub(r"<[^>]*>?", "", "") and not re.search(r"</?(script|iframe|img|a|b|i|div|p)\b", text, re.I), (lid, "no HTML allowed")
