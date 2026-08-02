from app.core.security import hash_password
from app.core.rate_limit import limiter
from app.models.org import Org
from app.models.user import User


def _seed_user(db_session, *, email: str, password: str, suffix: str):
    org = Org(id=f"org-{suffix}", name="Auth Org")
    user = User(
        id=f"user-{suffix}", org_id=org.id, email=email,
        hashed_password=hash_password(password), role="member",
    )
    db_session.add_all([org, user])
    db_session.commit()
    return org, user


def test_login_succeeds_with_correct_credentials(client, db_session):
    _org, _user = _seed_user(db_session, email="a@example.com", password="correct-horse", suffix="ok")

    resp = client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "correct-horse"})
    assert resp.status_code == 200
    assert resp.json()["token_type"] == "bearer"
    assert resp.json()["access_token"]


def test_login_fails_with_wrong_password(client, db_session):
    limiter.reset()
    _seed_user(db_session, email="b@example.com", password="correct-horse", suffix="wrongpw")

    resp = client.post("/api/v1/auth/login", json={"email": "b@example.com", "password": "wrong"})
    assert resp.status_code == 401


def test_login_fails_for_nonexistent_user(client, db_session):
    limiter.reset()
    resp = client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever"}
    )
    assert resp.status_code == 401


def test_login_is_rate_limited_after_repeated_attempts(client, db_session):
    limiter.reset()
    _seed_user(db_session, email="c@example.com", password="correct-horse", suffix="ratelimit")

    for _ in range(5):
        resp = client.post(
            "/api/v1/auth/login", json={"email": "c@example.com", "password": "wrong"}
        )
        assert resp.status_code == 401

    resp = client.post("/api/v1/auth/login", json={"email": "c@example.com", "password": "wrong"})
    assert resp.status_code == 429
