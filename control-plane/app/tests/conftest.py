import os
import tempfile

from cryptography.fernet import Fernet

# Must be set before the first `get_settings()` call anywhere in the app,
# since pydantic-settings reads process env at Settings() construction time
# and get_settings() is lru_cached.
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("CELL_STATE_ROOT", tempfile.mkdtemp(prefix="emailagent-cell-state-"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.models  # noqa: E402,F401 — registers every model on Base.metadata
from app.core.security import create_cell_service_token  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402


def cell_headers(org_id: str) -> dict[str, str]:
    """Auth header a cell's MCP server would send — see
    core.security.create_cell_service_token."""
    return {"X-Cell-Service-Token": create_cell_service_token(org_id=org_id)}


@pytest.fixture()
def db_session():
    """A single SQLite in-memory session shared by both the test body and
    the app's request handling (via a get_db override), so writes made
    directly in a test are immediately visible to API calls in the same
    test without needing a real transaction/isolation story."""
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def client(db_session):
    return TestClient(app)
