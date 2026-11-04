import signal
import threading
import time
import uuid
from unittest.mock import patch

import blurt_worker.main as wm
from blurt_core.db.models import Job, JobStatus, Recording, RecordingStatus, User
from sqlalchemy.orm import Session


def test_worker_starts_and_stops() -> None:
    wm._running = True
    # signal.signal only works on main thread; patch it out for test
    with patch.object(signal, "signal"):
        t = threading.Thread(target=wm.main, daemon=True)
        t.start()
        time.sleep(0.1)
        wm._running = False
        t.join(timeout=2)
    assert not t.is_alive()


def _seed(session: Session, status: RecordingStatus) -> tuple[uuid.UUID, uuid.UUID]:
    user = User(email=f"{uuid.uuid4()}@x.dev", password_hash="x")
    session.add(user)
    session.flush()
    rec = Recording(user_id=user.id, storage_key="k", mime_type="audio/flac", status=status)
    session.add(rec)
    session.flush()
    job = Job(
        kind="transcribe",
        payload={"recording_id": str(rec.id)},
        status=JobStatus.failed,
        attempts=3,
        max_attempts=3,
    )
    session.add(job)
    session.flush()
    return rec.id, job.id


def test_mark_recording_failed_moves_in_progress_to_failed(session: Session) -> None:
    rec_id, job_id = _seed(session, RecordingStatus.transcribing)
    wm._mark_recording_failed(session, job_id)
    session.refresh(session.get(Recording, rec_id))
    assert session.get(Recording, rec_id).status == RecordingStatus.failed


def test_mark_recording_failed_leaves_terminal_states_untouched(session: Session) -> None:
    rec_id, job_id = _seed(session, RecordingStatus.ready)
    wm._mark_recording_failed(session, job_id)
    assert session.get(Recording, rec_id).status == RecordingStatus.ready


def test_mark_recording_failed_ignores_jobs_without_recording(session: Session) -> None:
    job = Job(
        kind="summarize",
        payload={"user_id": str(uuid.uuid4())},
        status=JobStatus.failed,
        attempts=3,
        max_attempts=3,
    )
    session.add(job)
    session.flush()
    # Should not raise even though there's no recording_id in the payload.
    wm._mark_recording_failed(session, job.id)
