"""Tests for the transcribe handler using FakeStorage and a stub STT provider."""

import json
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from unittest.mock import patch

from blurt_core.db.models import Job, JobStatus, Recording, RecordingStatus, Transcript
from blurt_core.providers.storage import FakeStorage
from blurt_core.providers.stt import Segment, TranscriptionResult
from sqlalchemy.orm import Session


class _StubStt:
    model_name = "stub-whisper"

    def transcribe(self, audio_bytes: bytes) -> TranscriptionResult:
        return TranscriptionResult(
            text="hello world",
            segments=[Segment(start=0.0, end=1.5, text="hello world")],
            language="en",
        )


def _make_job(recording_id: uuid.UUID) -> Job:
    job = Job(
        kind="transcribe",
        payload={"recording_id": str(recording_id)},
        status=JobStatus.running,
        attempts=1,
        max_attempts=3,
    )
    job.id = uuid.uuid4()
    return job


def _patch_session(s: Session) -> Generator[None, None, None]:
    """Patch get_session so handlers use the test session (no commit, auto-rollback)."""

    @contextmanager
    def _fake_get_session() -> Generator[Session, None, None]:
        yield s

    return patch("blurt_core.db.session.get_session", _fake_get_session)


def test_handle_transcribe_writes_transcript(session: Session) -> None:
    from blurt_core.db.models import User
    from blurt_worker.handlers import transcribe as mod

    fake_storage = FakeStorage()

    user = User(email="test@example.com", password_hash="x")
    session.add(user)
    session.flush()

    recording = Recording(
        user_id=user.id,
        storage_key="recs/test.flac",
        mime_type="audio/flac",
        status=RecordingStatus.transcribing,
    )
    session.add(recording)
    session.flush()
    fake_storage.put("recs/test.flac", b"fake-audio", "audio/flac")

    job = _make_job(recording.id)

    with (
        patch.object(mod, "storage", fake_storage),
        patch.object(mod, "stt", _StubStt()),
        patch("blurt_worker.handlers.transcribe.get_session") as mock_gs,
    ):

        @contextmanager
        def _fake_gs() -> Generator[Session, None, None]:
            yield session

        mock_gs.side_effect = _fake_gs
        mod.handle_transcribe(job)

    transcript = session.query(Transcript).filter_by(recording_id=recording.id).one()
    assert transcript.text == "hello world"
    assert transcript.provider == "mlx"
    assert len(transcript.segments) == 1
    assert transcript.segments[0]["start"] == 0.0

    session.refresh(recording)
    assert recording.status == RecordingStatus.splitting

    split_job = session.query(Job).filter_by(kind="split").one()
    payload = (
        json.loads(split_job.payload) if isinstance(split_job.payload, str) else split_job.payload
    )
    assert payload["recording_id"] == str(recording.id)
