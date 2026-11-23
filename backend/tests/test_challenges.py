import pytest

from app.sim import challenge as ch

SEEDS = [0, 1, 2, 3, 7, 11, 25, 99]


@pytest.mark.parametrize("tid", list(ch.TEMPLATES))
def test_every_challenge_variation_has_an_affordable_solution_and_an_empty_answer_fails(tid):
    for seed in SEEDS:
        spec = ch.generate(tid, seed)
        sol = ch.feasible(tid, spec)
        assert sol is not None
        right = {s["id"]: "right" for s in spec["symptoms"]}
        win = ch.run(tid, seed, right, sol)
        assert win["stars"] == 3 and not win["over_budget"] and win["resolved"] == win["total"]
        assert ch.run(tid, seed, {}, [])["stars"] == 0


def test_challenges_are_repeatable_and_a_seed_changes_the_numbers():
    assert ch.public("flashsale", 3) == ch.public("flashsale", 3)
    a, b = ch.public("flashsale", 1), ch.public("flashsale", 2)
    assert [s["value"] for s in a["symptoms"]] != [s["value"] for s in b["symptoms"]] or a["budget"] != b["budget"]


def test_the_right_answer_depends_on_the_business_context():
    # a cache is a fine fix for a shop but breaks the bank's balance rule, which needs reads from the source of truth
    shop = ch.run("flashsale", 1, {}, ["cache", "invalidate", "ryw", "hotkey"])
    bank = ch.run("bank", 1, {}, ["cache", "invalidate", "ryw"])
    assert [r for r in shop["rows"] if r["id"] == "stale"][0]["resolved"]
    assert not [r for r in bank["rows"] if r["id"] == "stale"][0]["resolved"]


def test_every_fix_has_a_side_effect_that_can_make_something_worse():
    r = ch.run("flashsale", 1, {}, ["replicas"])
    assert [x for x in r["rows"] if x["id"] == "stale"][0]["after"] > [x for x in r["rows"] if x["id"] == "stale"][0]["before"]
    assert r["harms"]


def test_the_public_view_never_reveals_the_answers():
    pub = ch.public("bank", 4)
    text = str(pub)
    assert "fx" not in text and "threshold" in text
    assert all(len(s["causes"]) == 4 for s in pub["symptoms"])


def test_challenge_api_flow_and_xp(client, auth):
    assert len(client.get("/api/challenges").json()) == 3
    pub = client.get("/api/challenges/flashsale?seed=2").json()
    spec = ch.generate("flashsale", 2)
    sol = ch.feasible("flashsale", spec)
    body = {"seed": 2, "diagnosis": {s["id"]: "right" for s in pub["symptoms"]}, "measures": sol}
    sim = client.post("/api/challenges/flashsale/simulate", json=body).json()
    assert sim["stars"] == 3
    assert client.post("/api/challenges/flashsale/submit", json=body).status_code == 401
    res = client.post("/api/challenges/flashsale/submit", json={**body, "defense": "I chose idempotency keys because retries repeat the request, invalidated the cache so stock is not stale, and kept inside the budget."}, headers=auth).json()
    assert res["stars"] == 3 and res["xpGained"] == 75 and res["defense"]["stars"] >= 1
    again = client.post("/api/challenges/flashsale/submit", json=body, headers=auth).json()
    assert again["xpGained"] == 0
    assert client.get("/api/challenges/nope").status_code == 404
    m = client.get("/api/mastery", headers=auth).json()
    assert {d["id"] for d in m["dimensions"]} == {"understanding", "practice", "variations", "diagnosis", "design"}
    assert [c for c in m["challenges"] if c["id"] == "flashsale"][0]["best"] == 3
    assert client.get("/api/mastery").status_code == 401
