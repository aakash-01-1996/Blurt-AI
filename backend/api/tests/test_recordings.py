import uuid

import blurt_api.deps as deps
import pytest
from blurt_core.providers.storage import FakeStorage
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def fake_storage(monkeypatch: pytest.MonkeyPatch) -> FakeStorage:
    fs = FakeStorage()
    monkeypatch.setattr(deps, "storage", fs)
    # Also patch it in the router module
    import blurt_api.routers.recordings as rec_module

    monkeypatch.setattr(rec_module, "storage", fs)
    return fs


def test_health(api_client: TestClient) -> None:
    r = api_client.get("/health")
    assert r.status_code == 200


def test_upload_too_large(api_client: TestClient) -> None:
    big = b"x" * (26 * 1024 * 1024)
    r = api_client.post(
        "/api/v1/recordings",
        files={"file": ("rec.webm", big, "audio/webm")},
    )
    assert r.status_code == 413


def test_upload_returns_recording(api_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    # probe_duration needs real audio; stub it so we exercise the response path.
    import blurt_api.routers.recordings as rec_module

    monkeypatch.setattr(rec_module, "probe_duration", lambda data: 5.0)

    r = api_client.post(
        "/api/v1/recordings",
        files={"file": ("rec.webm", b"audio-bytes", "audio/webm")},
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "uploaded"
    assert body["duration_s"] == 5.0
    assert body["id"]


def test_upload_sanitizes_filename_extension(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch, fake_storage: FakeStorage
) -> None:
    import blurt_api.routers.recordings as rec_module

    monkeypatch.setattr(rec_module, "probe_duration", lambda data: 2.0)

    # A filename containing path separators and dot segments.
    r = api_client.post(
        "/api/v1/recordings",
        files={"file": ("a./../../../../tmp/pwned", b"audio-bytes", "audio/webm")},
    )
    assert r.status_code == 202, r.text

    key = next(iter(fake_storage._store))
    assert ".." not in key
    ext = key.rsplit(".", 1)[-1]
    assert ext.isalnum() and "/" not in ext


def test_upload_enforces_per_user_quota(monkeypatch: pytest.MonkeyPatch) -> None:
    import blurt_api.routers.recordings as rec_module
    from blurt_api.main import app

    monkeypatch.setattr(rec_module, "probe_duration", lambda data: 1.0)
    # Tight limit so the test is fast; fresh user so the count starts at zero.
    monkeypatch.setattr(rec_module.settings, "max_recordings_per_minute", 2)

    client = TestClient(app)
    signup = client.post(
        "/api/v1/auth/signup",
        json={"email": f"quota-{uuid.uuid4()}@blurt.dev", "password": "password123"},
    )
    assert signup.status_code == 201, signup.text
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    def upload() -> int:
        return client.post(
            "/api/v1/recordings",
            files={"file": ("rec.webm", b"audio-bytes", "audio/webm")},
            headers=headers,
        ).status_code

    assert upload() == 202
    assert upload() == 202
    # Third within the window is rejected, not processed.
    assert upload() == 429


def test_list_recordings_serializes_created_at(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import blurt_api.routers.recordings as rec_module

    monkeypatch.setattr(rec_module, "probe_duration", lambda data: 3.0)
    api_client.post(
        "/api/v1/recordings",
        files={"file": ("rec.webm", b"audio-bytes", "audio/webm")},
    )

    r = api_client.get("/api/v1/recordings")
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) >= 1
    assert isinstance(rows[0]["created_at"], str) and rows[0]["created_at"]
