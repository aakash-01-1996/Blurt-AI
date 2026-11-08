import json
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from blurt_core.db.models import (
    Item,
    ItemStatus,
    Job,
    JobStatus,
    Recording,
    RecordingStatus,
    Transcript,
    User,
)
from sqlalchemy.orm import Session


def _session_patcher(s: Session) -> object:
    @contextmanager
    def _fake_gs() -> Generator[Session, None, None]:
        yield s

    return patch("blurt_core.db.session.get_session", _fake_gs)


def _make_job(kind: str, payload: dict) -> Job:  # type: ignore[type-arg]
    job = Job(kind=kind, payload=payload, status=JobStatus.running, attempts=1, max_attempts=3)
    job.id = uuid.uuid4()
    return job


def _seed_recording(session: Session) -> Recording:
    user = User(email=f"{uuid.uuid4()}@test.com", password_hash="x")
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
    return recording


# ── split ─────────────────────────────────────────────────────────────────────


def test_handle_split_creates_items_and_enqueues_route(session: Session) -> None:
    from blurt_worker.handlers import split as mod

    recording = _seed_recording(session)
    transcript = Transcript(
        recording_id=recording.id,
        text="Fixed the login bug. Need to write tests.",
        segments=[],
        provider="groq",
        model="whisper-large-v3-turbo",
    )
    session.add(transcript)
    session.flush()

    llm_response = json.dumps(
        [
            {"text": "Fixed the login bug.", "start_char": 0, "end_char": 20},
            {"text": "Need to write tests.", "start_char": 21, "end_char": 41},
        ]
    )
    mock_llm = MagicMock()
    mock_llm.chat.return_value = llm_response

    job = _make_job("split", {"recording_id": str(recording.id)})

    with (
        patch.object(mod, "llm", mock_llm),
        patch("blurt_worker.handlers.split.get_session") as mock_gs,
    ):

        @contextmanager
        def _fake_gs() -> Generator[Session, None, None]:
            yield session

        mock_gs.side_effect = _fake_gs
        mod.handle_split(job)

    items = session.query(Item).filter_by(recording_id=recording.id).all()
    assert len(items) == 2
    assert items[0].span_text == "Fixed the login bug."
    assert items[1].span_text == "Need to write tests."

    route_jobs = session.query(Job).filter_by(kind="route").all()
    assert len(route_jobs) == 2

    session.refresh(recording)
    assert recording.status == RecordingStatus.routing


def test_handle_split_empty_llm_response_falls_back_to_whole_transcript(
    session: Session,
) -> None:
    from blurt_worker.handlers import split as mod

    recording = _seed_recording(session)
    session.add(
        Transcript(
            recording_id=recording.id,
            text="Just a quick note.",
            segments=[],
            provider="groq",
            model="whisper-large-v3-turbo",
        )
    )
    session.flush()

    mock_llm = MagicMock()
    mock_llm.chat.return_value = ""  # the prod failure: empty content, not JSON

    job = _make_job("split", {"recording_id": str(recording.id)})
    with (
        patch.object(mod, "llm", mock_llm),
        patch("blurt_worker.handlers.split.get_session") as mock_gs,
    ):

        @contextmanager
        def _fake_gs() -> Generator[Session, None, None]:
            yield session

        mock_gs.side_effect = _fake_gs
        mod.handle_split(job)  # must NOT raise

    items = session.query(Item).filter_by(recording_id=recording.id).all()
    assert len(items) == 1
    assert items[0].span_text == "Just a quick note."
    session.refresh(recording)
    assert recording.status == RecordingStatus.routing


# ── route ─────────────────────────────────────────────────────────────────────


def test_handle_route_high_confidence_enqueues_extract(session: Session) -> None:
    from blurt_worker.handlers import route as mod

    recording = _seed_recording(session)
    item = Item(
        recording_id=recording.id,
        section="unknown",
        span_text="Finished the auth refactor.",
    )
    session.add(item)
    session.flush()

    mock_llm = MagicMock()
    mock_llm.chat.return_value = json.dumps({"section": "work_log", "confidence": 0.95})

    job = _make_job("route", {"recording_id": str(recording.id), "item_id": str(item.id)})

    with (
        patch.object(mod, "llm", mock_llm),
        patch("blurt_worker.handlers.route.get_session") as mock_gs,
    ):

        @contextmanager
        def _fake_gs() -> Generator[Session, None, None]:
            yield session

        mock_gs.side_effect = _fake_gs
        mod.handle_route(job)

    session.refresh(item)
    assert item.section == "work_log"
    assert item.route_confidence == pytest.approx(0.95)

    extract_jobs = session.query(Job).filter_by(kind="extract").all()
    assert len(extract_jobs) == 1


def test_handle_route_skip_rejects_item(session: Session) -> None:
    from blurt_worker.handlers import route as mod

    recording = _seed_recording(session)
    item = Item(recording_id=recording.id, section="unknown", span_text="um yeah")
    session.add(item)
    session.flush()

    mock_llm = MagicMock()
    mock_llm.chat.return_value = json.dumps({"section": "skip", "confidence": 0.99})

    job = _make_job("route", {"recording_id": str(recording.id), "item_id": str(item.id)})

    with (
        patch.object(mod, "llm", mock_llm),
        patch("blurt_worker.handlers.route.get_session") as mock_gs,
    ):

        @contextmanager
        def _fake_gs() -> Generator[Session, None, None]:
            yield session

        mock_gs.side_effect = _fake_gs
        mod.handle_route(job)

    session.refresh(item)
    assert item.status == ItemStatus.rejected


def test_handle_route_unparseable_response_rejects_item(session: Session) -> None:
    from blurt_worker.handlers import route as mod

    recording = _seed_recording(session)
    item = Item(recording_id=recording.id, section="unknown", span_text="um yeah")
    session.add(item)
    session.flush()

    mock_llm = MagicMock()
    mock_llm.chat.return_value = ""  # empty / non-JSON from the model

    job = _make_job("route", {"recording_id": str(recording.id), "item_id": str(item.id)})
    with (
        patch.object(mod, "llm", mock_llm),
        patch("blurt_worker.handlers.route.get_session") as mock_gs,
    ):

        @contextmanager
        def _fake_gs() -> Generator[Session, None, None]:
            yield session

        mock_gs.side_effect = _fake_gs
        mod.handle_route(job)  # must NOT raise

    session.refresh(item)
    assert item.status == ItemStatus.rejected


# ── extract ───────────────────────────────────────────────────────────────────


def test_handle_extract_writes_fields_and_marks_ready(session: Session) -> None:
    from blurt_worker.handlers import extract as mod

    recording = _seed_recording(session)
    item = Item(
        recording_id=recording.id,
        section="work_log",
        span_text="Finished the auth refactor.",
        status=ItemStatus.pending,
    )
    session.add(item)
    session.flush()

    fields = {"accomplishment": "Finished the auth refactor", "project": "backend"}
    mock_llm = MagicMock()
    mock_llm.chat.return_value = json.dumps(fields)

    job = _make_job("extract", {"recording_id": str(recording.id), "item_id": str(item.id)})

    with (
        patch.object(mod, "llm", mock_llm),
        patch("blurt_worker.handlers.extract.get_session") as mock_gs,
    ):

        @contextmanager
        def _fake_gs() -> Generator[Session, None, None]:
            yield session

        mock_gs.side_effect = _fake_gs
        mod.handle_extract(job)

    session.refresh(item)
    assert item.fields == fields
    assert item.status == ItemStatus.pending

    session.refresh(recording)
    assert recording.status == RecordingStatus.ready
