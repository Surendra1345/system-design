import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app import deps, models  # noqa: F401  (register tables)
from app.db import Base, get_db, make_engine
from app.main import create_app
from app.config import get_settings
from app.security import TokenBucket


@pytest.fixture(autouse=True)
def no_real_ai(monkeypatch):
    """Tests never call the real API, even when a key is set in .env."""
    monkeypatch.setattr(get_settings(), "groq_api_key", None)


@pytest.fixture()
def engine(tmp_path):
    """SQLite by default. Set TEST_DATABASE_URL to run the whole suite on another database, such as PostgreSQL."""
    url = os.environ.get("TEST_DATABASE_URL")
    eng = make_engine(url or "sqlite:///%s/test.db" % tmp_path)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture()
def client(engine, monkeypatch):
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    app = create_app()

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    monkeypatch.setattr(deps, "login_limiter", TokenBucket(1000, 100))
    monkeypatch.setattr(deps, "_ai_limiter", None)
    c = TestClient(app)          # not used as a context manager, so the real database is never touched
    c.engine = engine
    c.Session = Session
    return c


@pytest.fixture()
def auth(client):
    """A registered learner. Returns (headers, username)."""
    r = client.post("/api/auth/register", json={"username": "alice", "password": "correct-horse"})
    assert r.status_code == 201
    return {"Authorization": "Bearer " + r.json()["token"]}
