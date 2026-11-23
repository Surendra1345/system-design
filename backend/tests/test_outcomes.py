from app import content
from app.services import mastery as mst

LESSONS = [l["id"] for l in content.lessons_doc()["lessons"]]


def test_every_lesson_has_outcomes_variations_and_earlier_prerequisites():
    oc = content.outcomes()
    assert set(oc) == set(LESSONS)
    for i, lid in enumerate(LESSONS):
        o = oc[lid]
        assert len(o["outcomes"]) >= 3 and all(x.startswith("Can ") and len(x) > 25 for x in o["outcomes"]), lid
        assert len(o["variations"]) >= 3 and all(len(v) > 12 for v in o["variations"]), lid
        for p in o["prereqs"]:
            assert p in LESSONS and LESSONS.index(p) < i, (lid, p)          # prerequisites exist and come earlier, so the map has no cycles


def test_lesson_api_returns_outcomes_and_prerequisite_titles(client):
    d = client.get("/api/lessons/cache").json()
    assert d["outcomes"]["outcomes"] and d["outcomes"]["variations"]
    assert d["outcomes"]["prereqs"][0] == {"id": "estimate", "title": "Back-of-the-envelope estimation"}


def test_mastery_needs_every_level_strong_not_one_good_run():
    assert mst.status(True, [3, 3, 2]) == mst.MASTERED
    assert mst.status(True, [3, 3, 0]) == mst.SHAKY          # good on two variations, failed the third: memorised, not understood
    assert mst.status(True, [1, 0, 0]) == mst.LEARNING
    assert mst.status(False, [0, 0, 0]) == mst.NEW
    assert mst.status(True, []) == mst.MASTERED and mst.status(False, []) == mst.NEW


def test_mastery_api_lists_concepts_and_flags_shaky_ones(client, auth):
    client.put("/api/lessons/lb/read", json={"done": True}, headers=auth)
    from app.sim import labs
    sol = labs.thresholds()["lb:0"]["solution"]
    client.post("/api/games/lb/lab/submit?level=0", json={"settings": sol}, headers=auth)
    m = client.get("/api/mastery", headers=auth).json()
    by = {c["id"]: c["status"] for c in m["concepts"]}
    assert len(m["concepts"]) == len(LESSONS) and by["lb"] == "shaky" and by["cache"] == "new"
    assert any(r["id"] == "lb" for r in m["review"])
    assert sum(m["concept_summary"].values()) == len(LESSONS)
