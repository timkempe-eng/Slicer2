"""In-memory job store and the background slicing task.

For the MVP, jobs live in a process-local dict. Swap this for Redis + a real
task queue (arq / RQ / Celery) and object storage before going multi-user;
the public functions here are the seam to do that behind.
"""
from __future__ import annotations

import threading
import uuid
from pathlib import Path
from typing import Optional

from . import config, slicer
from .models import Job, JobStatus, SliceOptions

_jobs: dict[str, Job] = {}
_lock = threading.Lock()


def create_job(filename: str, input_path: Path, options: SliceOptions) -> Job:
    job_id = uuid.uuid4().hex
    job = Job(
        id=job_id,
        filename=filename,
        input_path=str(input_path),
        options=options,
    )
    with _lock:
        _jobs[job_id] = job
    return job


def get_job(job_id: str) -> Optional[Job]:
    with _lock:
        return _jobs.get(job_id)


def list_jobs() -> list[Job]:
    with _lock:
        return sorted(_jobs.values(), key=lambda j: j.created_at, reverse=True)


def run_slice(job_id: str) -> None:
    """Execute slicing for a job. Intended to run in a background task."""
    job = get_job(job_id)
    if job is None:
        return

    job.touch(JobStatus.SLICING)
    output_path = config.OUTPUT_DIR / f"{job.id}.gcode.3mf"
    try:
        result = slicer.slice_model(Path(job.input_path), output_path, job.options)
        job.output_path = str(output_path)
        job.result = result
        job.touch(JobStatus.DONE)
    except slicer.SlicerError as exc:
        job.error = str(exc)
        job.touch(JobStatus.FAILED)
    except Exception as exc:  # noqa: BLE001 - surface unexpected failures to the client
        job.error = f"Unexpected slicing error: {exc}"
        job.touch(JobStatus.FAILED)
