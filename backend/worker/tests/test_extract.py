"""extract handler: a flubbed (non-JSON) LLM response must not wedge the
recording — the item is rejected and the recording still reaches ready."""

import uuid
from collections.abc import Generator
from contextlib import contextmanager
from unittest.mock import patch

from blurt_core.db.models import Item, ItemStatus, Job, JobStatus, Recording, RecordingStatus, User
from sqlalchemy.orm import Session


class _ProseStub:
    """Stands in for the LLM client, returning prose instead of JSON."""

    def chat(self, messages: object, **kwargs: object) -> str:
        return "Sure! I don't see a note here. Please share it and I'll extract the fields."


def _make_job(recording_id: uuid.UUID, item_id: uuid.UUID) -> Job:
    job = Job(
        kind="extract",
        payload={"recording_id": str(recording_id), "item_id": str(item_id)},
        status=JobStatus.running,
        attempts=1,
        max_attempts=3,
    )
    job.id = uuid.uuid4()
    return job


def test_unparseable_extract_rejects_item_and_completes(session: Session) -> None:
    from blurt_worker.handlers import extract as mod

    user = User(email="e@x.dev", password_hash="x")
    session.add(user)
    session.flush()

    recording = Recording(
        user_id=user.id,
        storage_key="k.flac",
        mime_type="audio/flac",
        status=RecordingStatus.routing,
    )
    session.add(recording)
    session.flush()

    item = Item(
        recording_id=recording.id,
        section="task",
        span_text="ship the thing tomorrow",
        status=ItemStatus.pending,
    )
    session.add(item)
    session.flush()

    job = _make_job(recording.id, item.id)

    with (
        patch.object(mod, "llm", _ProseStub()),
        patch("blurt_worker.handlers.extract.get_session") as mock_gs,
    ):

        @contextmanager
        def _fake_gs() -> Generator[Session, None, None]:
            yield session

        mock_gs.side_effect = _fake_gs
        mod.handle_extract(job)

    session.refresh(item)
    session.refresh(recording)
    assert item.status == ItemStatus.rejected
    assert item.fields is None
    # the only item is now rejected → recording completes instead of hanging
    assert recording.status == RecordingStatus.ready
