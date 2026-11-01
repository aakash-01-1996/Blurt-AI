import threading
import uuid

from blurt_core.db.models import Job, JobStatus
from blurt_core.queue import claim, complete, enqueue, fail, recover_stuck
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker


def test_enqueue_creates_queued_job(session: Session) -> None:
    job = enqueue(session, "test_kind", {"key": "value"})
    session.commit()
    assert job.id is not None
    assert job.status == JobStatus.queued
    assert job.attempts == 0


def test_claim_returns_job(session: Session) -> None:
    enqueue(session, "test_kind", {})
    session.commit()
    job = claim(session, "worker-1")
    session.commit()
    assert job is not None
    assert job.status == JobStatus.running
    assert job.locked_by == "worker-1"


def test_claim_exclusivity(db_engine: Engine) -> None:
    """Two concurrent workers must never claim the same job."""
    SessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)

    # Mark all existing queued jobs completed so only our job is claimable
    s = SessionLocal()
    s.execute(text("UPDATE jobs SET status = 'completed' WHERE status = 'queued'"))
    s.commit()
    s.close()

    s = SessionLocal()
    enqueue(s, "exclusive_test", {})
    s.commit()
    s.close()

    claimed: list[uuid.UUID | None] = []
    errors: list[Exception] = []

    def worker(worker_id: str) -> None:
        try:
            ws = SessionLocal()
            job = claim(ws, worker_id)
            ws.commit()
            claimed.append(job.id if job else None)
            ws.close()
        except Exception as exc:
            errors.append(exc)

    t1 = threading.Thread(target=worker, args=("w1",))
    t2 = threading.Thread(target=worker, args=("w2",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert not errors
    non_none = [c for c in claimed if c is not None]
    assert len(non_none) == 1, "exactly one worker should have claimed the job"


def test_complete_marks_job_completed(session: Session) -> None:
    enqueue(session, "test_kind", {})
    session.commit()
    job: Job | None = claim(session, "worker-1")
    session.commit()
    assert job is not None
    complete(session, job.id)
    session.commit()
    session.refresh(job)
    assert job.status == JobStatus.completed


def test_fail_retries_with_backoff(session: Session) -> None:
    enqueue(session, "test_kind", {}, max_attempts=3)
    session.commit()

    # First claim + fail
    job: Job | None = claim(session, "worker-1")
    session.commit()
    assert job is not None
    assert fail(session, job.id, "error 1") is False  # retry, not permanent
    session.commit()
    session.refresh(job)
    assert job.status == JobStatus.queued
    assert job.attempts == 1

    # Reset run_after so next claim works immediately
    session.execute(text("UPDATE jobs SET run_after = now() WHERE id = :id"), {"id": job.id})
    session.commit()

    # Second claim + fail
    job2: Job | None = claim(session, "worker-1")
    session.commit()
    assert job2 is not None
    fail(session, job2.id, "error 2")
    session.commit()
    session.refresh(job2)
    assert job2.status == JobStatus.queued
    assert job2.attempts == 2

    session.execute(text("UPDATE jobs SET run_after = now() WHERE id = :id"), {"id": job2.id})
    session.commit()

    # Third claim + fail → permanently failed
    job3: Job | None = claim(session, "worker-1")
    session.commit()
    assert job3 is not None
    assert fail(session, job3.id, "error 3") is True  # permanently failed
    session.commit()
    session.refresh(job3)
    assert job3.status == JobStatus.failed


def test_recover_stuck(session: Session) -> None:
    enqueue(session, "stuck_test", {})
    session.commit()
    job: Job | None = claim(session, "worker-old")
    session.commit()
    assert job is not None

    session.execute(
        text("UPDATE jobs SET locked_at = now() - interval '20 minutes' WHERE id = :id"),
        {"id": job.id},
    )
    session.commit()

    count = recover_stuck(session, timeout_minutes=10)
    session.commit()
    assert count >= 1
    session.refresh(job)
    assert job.status == JobStatus.queued
    assert job.locked_by is None
