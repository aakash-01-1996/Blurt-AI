import os
import uuid
from collections.abc import Generator

import pytest
from blurt_core.config import settings
from blurt_core.db.models import Base, User
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def _test_db_url() -> str:
    return os.environ.get(
        "TEST_DATABASE_URL", settings.database_url.replace("/blurt", "/blurt_test")
    )


@pytest.fixture(scope="session")
def test_engine() -> Generator[Engine, None, None]:
    engine = create_engine(_test_db_url(), pool_pre_ping=True)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def db_session(test_engine: Engine) -> Generator[Session, None, None]:
    SessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


@pytest.fixture(autouse=True)
def _patch_api_db(monkeypatch: pytest.MonkeyPatch, test_engine: Engine) -> None:
    """Redirect all get_session calls in the API to the test database."""
    from contextlib import contextmanager

    import blurt_api.auth as auth_mod
    import blurt_api.routers.auth as auth_router_mod
    import blurt_api.routers.export as export_mod
    import blurt_api.routers.items as items_mod
    import blurt_api.routers.lists as lists_mod
    import blurt_api.routers.notes as notes_mod
    import blurt_api.routers.passkey as passkey_mod
    import blurt_api.routers.recordings as recordings_mod
    import blurt_api.routers.summaries as summaries_mod
    import blurt_api.routers.tasks as tasks_mod
    import blurt_api.routers.work_log as work_log_mod
    import blurt_core.db.session as session_mod

    TestSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)

    @contextmanager
    def _test_get_session() -> Generator[Session, None, None]:
        s = TestSession()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    monkeypatch.setattr(session_mod, "get_session", _test_get_session)
    monkeypatch.setattr(auth_mod, "get_session", _test_get_session)
    monkeypatch.setattr(auth_router_mod, "get_session", _test_get_session)
    monkeypatch.setattr(export_mod, "get_session", _test_get_session)
    monkeypatch.setattr(items_mod, "get_session", _test_get_session)
    monkeypatch.setattr(lists_mod, "get_session", _test_get_session)
    monkeypatch.setattr(notes_mod, "get_session", _test_get_session)
    monkeypatch.setattr(passkey_mod, "get_session", _test_get_session)
    monkeypatch.setattr(recordings_mod, "get_session", _test_get_session)
    monkeypatch.setattr(summaries_mod, "get_session", _test_get_session)
    monkeypatch.setattr(tasks_mod, "get_session", _test_get_session)
    monkeypatch.setattr(work_log_mod, "get_session", _test_get_session)


@pytest.fixture(autouse=True)
def _disable_recording_quota(monkeypatch: pytest.MonkeyPatch) -> None:
    """Per-user recording quotas are a production safety feature; disable them by
    default so unrelated tests aren't throttled. The quota test opts back in."""
    from blurt_core.config import settings

    monkeypatch.setattr(settings, "max_recordings_per_minute", 0)
    monkeypatch.setattr(settings, "max_recordings_per_day", 0)


# Fixed test user ID (matches seed migration for legacy tests)
TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _ensure_test_user(session: Session) -> None:
    if not session.get(User, TEST_USER_ID):
        session.add(User(id=TEST_USER_ID, email="test@blurt.dev", password_hash="x"))
        session.commit()


@pytest.fixture()
def auth_headers(db_session: Session) -> dict[str, str]:
    """Return Authorization headers for the fixed test user."""
    from blurt_api.auth import create_access_token

    _ensure_test_user(db_session)
    token = create_access_token(TEST_USER_ID)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def api_client(auth_headers: dict[str, str]) -> TestClient:
    """TestClient pre-configured with auth headers."""
    from blurt_api.main import app

    return TestClient(app, headers=auth_headers)
