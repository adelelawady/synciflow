from __future__ import annotations

import uuid

from sqlmodel import Session, select

from synciflow.db.models import Job, utcnow


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
    session.commit()
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
    session.commit()


def complete_job(session: Session, job_id: str) -> None:
    """Mark job as completed (status='completed', progress=1.0)."""
    job = session.exec(select(Job).where(Job.job_id == job_id)).first()
    if job is None:
        return
    job.status = "completed"
    job.progress = 1.0
    job.updated_at = utcnow()
    session.add(job)
    session.commit()


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
    session.commit()


def get_job(session: Session, job_id: str) -> Job | None:
    """Fetch a job by job_id."""
    return session.exec(select(Job).where(Job.job_id == job_id)).first()
