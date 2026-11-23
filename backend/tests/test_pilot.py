from sqlalchemy import select

from app import models
from app.routers import pilot
from app.security import TokenBucket
from tools import pilot_report


def _rows(client):
    with client.Session() as db:
        return db.scalars(select(models.Feedback)).all()


def test_anyone_can_send_feedback_and_a_signed_in_tester_is_linked(client, auth):
    assert client.post("/api/feedback", json={"page": "/lesson/cache", "kind": "unclear", "message": "what is TTL?"}).status_code == 201
    assert client.post("/api/feedback", headers=auth, json={"page": "/", "kind": "liked", "rating": 5}).status_code == 201
    anon, linked = _rows(client)
    assert anon.user_id is None and anon.kind == "unclear"
    assert linked.user_id is not None and linked.rating == 5


def test_feedback_is_validated(client):
    bad = [{"page": "lesson", "kind": "bug"}, {"page": "/x", "kind": "rant"},
           {"page": "/x", "kind": "bug", "rating": 9}, {"page": "/x", "kind": "bug", "message": "a" * 1001},
           {"page": "/<script>", "kind": "bug"}]
    for b in bad:
        assert client.post("/api/feedback", json=b).status_code == 422
    assert _rows(client) == []


def test_feedback_is_rate_limited(client, monkeypatch):
    monkeypatch.setattr(pilot, "_limiter", TokenBucket(2, 0.0001))
    codes = [client.post("/api/feedback", json={"page": "/", "kind": "idea"}).status_code for _ in range(4)]
    assert codes[:2] == [201, 201] and codes[-1] == 429


def test_report_ranks_the_least_clear_page_first(client):
    for kind in ("unclear", "unclear", "clear"):
        client.post("/api/feedback", json={"page": "/lesson/cache", "kind": kind})
    for kind in ("clear", "clear", "unclear"):
        client.post("/api/feedback", json={"page": "/lesson/lb", "kind": kind})
    ranked = pilot_report.build(_rows(client))
    assert ranked[0][0] == "/lesson/cache" and ranked[0][2] == 2
