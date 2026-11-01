import json
import logging
import signal
import time
import traceback
import uuid
from collections.abc import Callable

from blurt_core.config import settings
from blurt_core.db.models import Job, Recording, RecordingStatus
from blurt_core.db.session import get_session
from blurt_core.logging import configure_logging
from blurt_core.queue import claim, complete, fail, recover_stuck
from sqlalchemy.orm import Session

from blurt_worker.handlers.extract import handle_extract
from blurt_worker.handlers.normalize import handle_normalize
from blurt_worker.handlers.route import handle_route
from blurt_worker.handlers.split import handle_split
from blurt_worker.handlers.summarize import handle_summarize
from blurt_worker.handlers.transcribe import handle_transcribe

configure_logging()
logger = logging.getLogger(__name__)

_running = True
_WORKER_ID = f"worker-{__name__}"

_handlers: dict[str, Callable[[Job], None]] = {
    "normalize": handle_normalize,
    "transcribe": handle_transcribe,
    "split": handle_split,
    "route": handle_route,
    "extract": handle_extract,
    "summarize": handle_summarize,
}

# Restrict to specific job kinds if HANDLED_KINDS is set (e.g. "normalize,transcribe")
_HANDLED_KINDS: list[str] | None = (
    [k.strip() for k in settings.handled_kinds.split(",") if k.strip()]
    if settings.handled_kinds
    else None
)


def _handle_sigterm(sig: int, frame: object) -> None:
    global _running
    logger.info("SIGTERM received, shutting down")
    _running = False


def _mark_recording_failed(session: Session, job_id: uuid.UUID) -> None:
    """After a job permanently fails, move its recording to the terminal
    'failed' state. This is the safety net that guarantees a recording can
    never hang in an in-progress status (transcribing/splitting/routing/…),
    whatever the stage or cause of the failure."""
    job = session.get(Job, job_id)
    if job is None:
        return
    payload = json.loads(job.payload) if isinstance(job.payload, str) else job.payload
    rid = payload.get("recording_id") if isinstance(payload, dict) else None
    if not rid:
        return  # jobs not tied to a recording (e.g. summarize)
    recording = session.get(Recording, uuid.UUID(str(rid)))
    if recording and recording.status not in (RecordingStatus.ready, RecordingStatus.failed):
        recording.status = RecordingStatus.failed
        session.flush()
        logger.error(
            "recording marked failed after permanent job failure",
            extra={"recording_id": str(rid), "kind": job.kind},
        )


def _process_one() -> bool:
    """Claim and process one job. Returns True if a job was processed."""
    with get_session() as session:
        job = claim(session, _WORKER_ID, kinds=_HANDLED_KINDS)
        if job is None:
            return False
        job_id = job.id
        kind = job.kind

    handler = _handlers.get(kind)
    if handler is None:
        with get_session() as session:
            if fail(session, job_id, f"unknown job kind: {kind}"):
                _mark_recording_failed(session, job_id)
        logger.error("no handler for job kind", extra={"kind": kind})
        return True

    try:
        with get_session() as session:
            job_obj = session.get(Job, job_id)
            if job_obj is None:
                return True
            session.expunge(job_obj)
        handler(job_obj)
        with get_session() as session:
            complete(session, job_id)
    except Exception:
        with get_session() as session:
            if fail(session, job_id, traceback.format_exc()):
                _mark_recording_failed(session, job_id)
        logger.exception("job failed", extra={"job_id": str(job_id), "kind": kind})

    return True


def main() -> None:
    signal.signal(signal.SIGTERM, _handle_sigterm)
    logger.info(
        "worker started",
        extra={"handled_kinds": _HANDLED_KINDS or "all"},
    )

    last_recover = 0.0

    while _running:
        now = time.monotonic()
        if now - last_recover >= 60:
            with get_session() as session:
                recover_stuck(session)
            last_recover = now

        try:
            processed = _process_one()
        except Exception:
            logger.exception("unexpected error in worker loop")
            processed = False

        if not processed:
            time.sleep(1)

    logger.info("worker stopped")


if __name__ == "__main__":
    main()
