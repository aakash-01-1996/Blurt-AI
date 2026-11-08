import uuid
from collections.abc import Generator
from contextlib import contextmanager
from unittest.mock import patch

from blurt_core.db.models import Job, JobStatus, Recording, RecordingStatus, User
from blurt_core.providers.storage import FakeStorage
from sqlalchemy.orm import Session


def _make_job(recording_id: uuid.UUID) -> Job:
    job = Job(
        kind="normalize",
        payload={"recording_id": str(recording_id)},
        status=JobStatus.running,
        attempts=1,
        max_attempts=3,
    )
    job.id = uuid.uuid4()
    return job


def test_handle_normalize_stores_flac_and_enqueues_transcribe(session: Session) -> None:
    from blurt_worker.handlers import normalize as mod

    fake_storage = FakeStorage()
    fake_storage.put("recs/test.webm", b"raw-audio", "audio/webm")

    user = User(email=f"{uuid.uuid4()}@test.com", password_hash="x")
    session.add(user)
    session.flush()

    recording = Recording(
        user_id=user.id,
        storage_key="recs/test.webm",
        mime_type="audio/webm",
        status=RecordingStatus.uploaded,
    )
    session.add(recording)
    session.flush()

    job = _make_job(recording.id)

    with (
        patch.object(mod, "storage", fake_storage),
        patch("blurt_worker.handlers.normalize.normalize", return_value=b"flac-audio"),
        patch("blurt_worker.handlers.normalize.get_session") as mock_gs,
    ):

        @contextmanager
        def _fake_gs() -> Generator[Session, None, None]:
            yield session

        mock_gs.side_effect = _fake_gs
        mod.handle_normalize(job)

    session.refresh(recording)
    assert recording.storage_key == "recs/test.flac"
    assert recording.status == RecordingStatus.transcribing

    assert fake_storage.get("recs/test.flac") == b"flac-audio"
    try:
        fake_storage.get("recs/test.webm")
        assert False, "original should have been deleted"
    except KeyError:
        pass

    # Scope to this recording — a shared test DB may hold transcribe jobs that
    # other tests (e.g. the API retry endpoint) committed.
    transcribe_job = (
        session.query(Job)
        .filter(
            Job.kind == "transcribe",
            Job.payload["recording_id"].astext == str(recording.id),
        )
        .one()
    )
    payload = transcribe_job.payload
    if isinstance(payload, str):
        import json

        payload = json.loads(payload)
    assert payload["recording_id"] == str(recording.id)
