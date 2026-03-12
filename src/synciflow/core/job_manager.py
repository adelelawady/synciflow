from __future__ import annotations

import time
import uuid

from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import PendingRollbackError
from sqlmodel import Session, select

from synciflow.db.models import Job, utcnow


def _commit_with_retry(session: Session, attempts: int = 8, base_sleep_s: float = 0.05) -> None:
    """
    SQLite allows only one writer at a time. When background jobs update progress while
    other writes are happening, commits can fail with 'database is locked'.
    Retry with a small backoff instead of crashing the job runner.
    """
    for i in range(attempts):
        try:
            session.commit()
            return
        except PendingRollbackError:
            # A previous flush/commit failed; the Session must be rolled back
            # before it can start a new transaction.
            session.rollback()
        except OperationalError as e:
            msg = str(e).lower()
            if "database is locked" not in msg and "database locked" not in msg:
                raise
            # Clear the failed transaction state before retrying.
            session.rollback()
            # Backoff: 50ms, 100ms, 200ms... capped by attempts.
            time.sleep(base_sleep_s * (2**i))
    # Final attempt without swallowing the error
    session.commit()


def create_job(session: Session, job_type: str) -> Job:
    """Create a new job with status 'pending'. Returns the Job with job_id set."""
    job_id = str(uuid.uuid4())
    job = Job(
        job_id=job_id,
        job_type=job_type,
        status="pending",
        progress=0.0,
        message=None,
    )
    session.add(job)
    _commit_with_retry(session)
    session.refresh(job)
    return job


def update_job_progress(
    session: Session,
    job_id: str,
    progress: float,
    message: str | None = None,
) -> None:
    """Update job progress and optional message. Sets status to 'running' if still pending."""
    job = session.exec(select(Job).where(Job.job_id == job_id)).first()
    if job is None:
        return
    job.progress = progress
    if message is not None:
        job.message = message
    if job.status == "pending":
        job.status = "running"
    job.updated_at = utcnow()
    session.add(job)
    _commit_with_retry(session)


def complete_job(session: Session, job_id: str) -> None:
    """Mark job as completed (status='completed', progress=1.0)."""
    job = session.exec(select(Job).where(Job.job_id == job_id)).first()
    if job is None:
        return
    job.status = "completed"
    job.progress = 1.0
    job.updated_at = utcnow()
    session.add(job)
    _commit_with_retry(session)


def fail_job(session: Session, job_id: str, message: str | None = None) -> None:
    """Mark job as failed. Optional message for error details."""
    job = session.exec(select(Job).where(Job.job_id == job_id)).first()
    if job is None:
        return
    job.status = "failed"
    if message is not None:
        job.message = message
    job.updated_at = utcnow()
    session.add(job)
    _commit_with_retry(session)


def get_job(session: Session, job_id: str) -> Job | None:
    """Fetch a job by job_id."""
    return session.exec(select(Job).where(Job.job_id == job_id)).first()
