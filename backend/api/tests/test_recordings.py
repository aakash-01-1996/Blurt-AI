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
