from datetime import datetime, timedelta, timezone

from app import deps
from app.models import SessionToken, User
from app.security import TokenBucket


def test_health(client):
    assert client.get("/api/health").json() == {"ok": True}


def test_register_validation_and_duplicates(client):
    bad = [{"username": "a", "password": "correct-horse"}, {"username": "bob", "password": "short"},
           {"username": "bad name!", "password": "correct-horse"}]
    for body in bad:
        assert client.post("/api/auth/register", json=body).status_code in (400, 422)
    ok = client.post("/api/auth/register", json={"username": "bob", "password": "correct-horse"})
    assert ok.status_code == 201 and ok.json()["token"]
    assert client.post("/api/auth/register", json={"username": "BOB", "password": "correct-horse"}).status_code == 409


def test_passwords_and_tokens_are_stored_hashed(client, auth):
    with client.Session() as db:
        u = db.query(User).filter_by(username="alice").one()
        assert "correct-horse" not in u.password_hash and len(u.password_hash) == 128
        token = auth["Authorization"].split()[1]
        assert all(s.token_hash != token and len(s.token_hash) == 64 for s in db.query(SessionToken))


def test_login_logout_and_expiry(client, auth):
    assert client.post("/api/auth/login", json={"username": "alice", "password": "wrong-password"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "nobody", "password": "wrong-password"}).status_code == 401
    login = client.post("/api/auth/login", json={"username": "ALICE", "password": "correct-horse"})
    h2 = {"Authorization": "Bearer " + login.json()["token"]}
    assert client.get("/api/progress", headers=h2).status_code == 200
    assert client.post("/api/auth/logout", headers=h2).status_code == 200
    assert client.get("/api/progress", headers=h2).status_code == 401
    with client.Session() as db:                      # expire the other session
        for s in db.query(SessionToken):
            s.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/progress", headers=auth).status_code == 401


def test_login_is_rate_limited(client, monkeypatch):
    monkeypatch.setattr(deps, "login_limiter", TokenBucket(5, 0.001))
    codes = [client.post("/api/auth/login", json={"username": "x", "password": "y"}).status_code for _ in range(8)]
    assert codes[:5] == [401] * 5 and 429 in codes[5:]


def test_protected_routes_need_a_token(client):
    for method, path in [("get", "/api/progress"), ("put", "/api/time/lb"), ("put", "/api/lessons/lb/read"),
                         ("post", "/api/games/numbers/builder/submit"), ("post", "/api/ai/tutor")]:
        assert getattr(client, method)(path, **({} if method == "get" else {"json": {}})).status_code in (401, 422)
    assert client.get("/api/progress", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_reading_gives_xp_once_even_if_reticked(client, auth):
    def read(done):
        return client.put("/api/lessons/net/read", json={"done": done}, headers=auth).json()["xpGained"]

    assert (read(True), read(False), read(True)) == (5, 0, 0)
    assert client.put("/api/lessons/unknown/read", json={"done": True}, headers=auth).status_code == 404


def test_study_time_is_the_learners_choice_and_validated(client, auth):
    put = lambda body: client.put("/api/time/cache", json=body, headers=auth)
    assert put({"targetMin": 90, "addSec": 600}).json() == {"targetMin": 90, "spentSec": 600}
    assert put({"addSec": 300}).json() == {"targetMin": 90, "spentSec": 900}
    assert put({"targetMin": 0}).json()["targetMin"] is None
    assert put({"targetMin": -5}).status_code == 422
    assert put({"addSec": 99999}).status_code == 422


def test_projects_pay_once(client, auth):
    put = lambda pid, done: client.put("/api/projects/" + pid, json={"done": done}, headers=auth)
    assert put("p-crud", True).json()["xpGained"] == 15
    assert put("p-crud", False).json()["xpGained"] == 0
    assert put("p-crud", True).json()["xpGained"] == 0
    assert put("zzz", True).status_code == 404
    assert client.get("/api/progress", headers=auth).json()["projects"] == ["p-crud"]


def test_leaderboard_orders_by_xp(client):
    a = client.post("/api/auth/register", json={"username": "low", "password": "correct-horse"}).json()["token"]
    b = client.post("/api/auth/register", json={"username": "high", "password": "correct-horse"}).json()["token"]
    for token, pid in ((a, "p-crud"), (b, "p-crud"), (b, "p-lb")):
        client.put("/api/projects/" + pid, json={"done": True}, headers={"Authorization": "Bearer " + token})
    board = client.get("/api/leaderboard").json()
    assert [r["username"] for r in board] == ["high", "low"] and board[0]["xp"] == 30


def test_catalog_and_lessons(client):
    cat = client.get("/api/catalog").json()
    assert len(cat["tracks"]) == 10 and len(cat["lessons"]) == 61
    assert all(l["game"] for l in cat["lessons"] if not l["projects"])
    lesson = client.get("/api/lessons/cache").json()
    assert lesson["sec"] and lesson["breaks"] and "mins" not in lesson
    assert client.get("/api/lessons/projects").json()["project_list"]
    assert client.get("/api/lessons/nope").status_code == 404
    assert client.get("/api/nothing").status_code == 404


def test_no_schedule_or_duration_language_in_content(client):
    import json, re
    blob = json.dumps(client.get("/api/catalog").json())
    assert not re.search(r"\bweeks?\b|hours per week|\d+ min read", blob, re.I)


def test_the_database_itself_rejects_usernames_that_differ_only_by_case(client):
    from sqlalchemy.exc import IntegrityError
    with client.Session() as db:
        db.add(User(username="Casey", salt="s", password_hash="h"))
        db.commit()
        db.add(User(username="casey", salt="s", password_hash="h"))
        try:
            db.commit()
            raised = False
        except IntegrityError:
            db.rollback()
            raised = True
    assert raised


def test_every_lesson_explains_what_why_and_when(client):
    for meta in client.get("/api/catalog").json()["lessons"]:
        e = client.get("/api/lessons/" + meta["id"]).json()["explain"]
        assert e, meta["id"]
        assert len(e["what"]) > 30 and len(e["why"]) > 30 and len(e["example"]) > 20, meta["id"]
        assert e["use"] and len(e["takeaways"]) == 3, meta["id"]
        assert all(isinstance(x, str) and x for x in e["use"] + e["avoid"] + e["takeaways"]), meta["id"]
