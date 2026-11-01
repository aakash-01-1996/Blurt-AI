import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from blurt_core.db.models import Job, JobStatus

logger = logging.getLogger(__name__)


def enqueue(
    session: Session,
    kind: str,
    payload: dict,  # type: ignore[type-arg]
    *,
    run_after: datetime | None = None,
    max_attempts: int = 3,
) -> Job:
    job = Job(
        kind=kind,
        payload=payload,
        status=JobStatus.queued,
        run_after=run_after or datetime.now(UTC),
        max_attempts=max_attempts,
    )
    session.add(job)
    session.flush()
    logger.info("enqueued job", extra={"job_id": str(job.id), "kind": kind})
    return job


def claim(
    session: Session,
    worker_id: str,
    *,
    kinds: list[str] | None = None,
) -> Job | None:
    """Claim the next available job. Pass `kinds` to restrict to specific job types."""
    kinds_filter = "AND kind = ANY(:kinds)" if kinds else ""
    result = session.execute(
        text(f"""
            UPDATE jobs
            SET status = 'running',
                locked_at = now(),
                locked_by = :worker_id,
                attempts = attempts + 1
            WHERE id = (
                SELECT id FROM jobs
                WHERE status = 'queued' AND run_after <= now()
                {kinds_filter}
                ORDER BY created_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING *
        """),
        {"worker_id": worker_id, "kinds": kinds},
    )
    row = result.mappings().first()
    if row is None:
        return None
    job = session.get(Job, row["id"])
    logger.info("claimed job", extra={"job_id": str(row["id"]), "worker": worker_id})
    return job


def complete(session: Session, job_id: uuid.UUID) -> None:
    job = session.get(Job, job_id)
    if job is None:
        return
    job.status = JobStatus.completed
    job.locked_at = None
    job.locked_by = None
    session.flush()
    logger.info("completed job", extra={"job_id": str(job_id)})


def fail(session: Session, job_id: uuid.UUID, error: str) -> bool:
    """Record a job failure. Returns True if the job has now permanently failed
    (attempts exhausted), False if it was re-queued for another retry."""
    job = session.get(Job, job_id)
    if job is None:
        return False
    job.last_error = error
    if job.attempts >= job.max_attempts:
        job.status = JobStatus.failed
        logger.warning("job permanently failed", extra={"job_id": str(job_id), "error": error})
        session.flush()
        return True
    job.status = JobStatus.queued
    backoff_seconds = 2**job.attempts * 5  # 10s, 20s, 40s, …
    job.run_after = datetime.now(UTC) + timedelta(seconds=backoff_seconds)
    job.locked_at = None
    job.locked_by = None
    logger.warning(
        "job failed, will retry",
        extra={"job_id": str(job_id), "attempts": job.attempts, "error": error},
    )
    session.flush()
    return False


def recover_stuck(session: Session, *, timeout_minutes: int = 10) -> int:
    cutoff = datetime.now(UTC) - timedelta(minutes=timeout_minutes)
    result = session.execute(
        text("""
            UPDATE jobs
            SET status = 'queued', locked_at = NULL, locked_by = NULL
            WHERE status = 'running' AND locked_at < :cutoff
        """),
        {"cutoff": cutoff},
    )
    count: int = result.rowcount  # type: ignore[attr-defined]
    if count:
        logger.warning("recovered stuck jobs", extra={"count": count})
    return count
