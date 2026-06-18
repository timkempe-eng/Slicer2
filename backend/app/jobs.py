"""Job store and the slicing task, backed by Postgres + object storage.

This is the persistence/queue seam. The public functions keep the same names
the rest of the app already calls (``create_job`` / ``get_job`` / ``list_jobs``
/ ``run_slice``); behind them, jobs live in the database (``db_models.JobRow``)
and model files live in object storage (``storage``). Slicing is dispatched via
``enqueue_slice`` — to an RQ worker when Redis is configured, inline otherwise.
"""
from __future__ import annotations

import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional

from . import config, queue, slicer, storage
from .db import SessionLocal, ensure_schema
from .db_models import JobRow
from .models import Job, JobStatus, SliceOptions, SliceResult


def _to_job(row: JobRow) -> Job:
    return Job(
        id=row.id,
        filename=row.filename,
        input_path=row.input_key or "",
        options=SliceOptions.model_validate(row.options),
        status=JobStatus(row.status),
        created_at=row.created_at,
        updated_at=row.updated_at,
        output_path=row.output_key,
        error=row.error,
        result=SliceResult.model_validate(row.result) if row.result else None,
    )


def create_job(filename: str, input_key: str, options: SliceOptions) -> Job:
    """Persist a queued job whose uploaded model lives at ``input_key``."""
    ensure_schema()
    now = time.time()
    row = JobRow(
        id=uuid.uuid4().hex,
        filename=filename,
        status=JobStatus.QUEUED,
        created_at=now,
        updated_at=now,
        options=options.model_dump(mode="json"),
        input_key=input_key,
    )
    with SessionLocal() as s:
        s.add(row)
        s.commit()
        return _to_job(row)


def get_job(job_id: str) -> Optional[Job]:
    ensure_schema()
    with SessionLocal() as s:
        row = s.get(JobRow, job_id)
        return _to_job(row) if row else None


def list_jobs() -> list[Job]:
    ensure_schema()
    with SessionLocal() as s:
        rows = s.query(JobRow).order_by(JobRow.created_at.desc()).all()
        return [_to_job(r) for r in rows]


def enqueue_slice(job_id: str) -> None:
    """Dispatch slicing — to the RQ worker, or inline when Redis is unset."""
    queue.enqueue(run_slice, job_id)


def _update(job_id: str, **fields) -> None:
    with SessionLocal() as s:
        row = s.get(JobRow, job_id)
        if row is None:
            return
        for k, v in fields.items():
            setattr(row, k, v)
        row.updated_at = time.time()
        s.commit()


def run_slice(job_id: str) -> None:
    """Slice a job. Runs in the RQ worker (or inline). Pulls the model from
    storage, slices into a temp dir, and pushes the result back to storage."""
    job = get_job(job_id)
    if job is None:
        return

    _update(job_id, status=JobStatus.SLICING)
    output_key = f"outputs/{job.id}.gcode.3mf"
    work = Path(tempfile.mkdtemp(prefix="slice-", dir=config.DATA_DIR))
    try:
        local_in = storage.download_to(job.input_path, work / Path(job.filename).name)
        local_out = work / f"{job.id}.gcode.3mf"
        result = slicer.slice_model(local_in, local_out, job.options)
        storage.upload_file(output_key, local_out)
        _update(
            job_id,
            status=JobStatus.DONE,
            output_key=output_key,
            result=result.model_dump(mode="json"),
        )
    except slicer.SlicerError as exc:
        _update(job_id, status=JobStatus.FAILED, error=str(exc))
    except Exception as exc:  # noqa: BLE001 - surface unexpected failures to the client
        _update(job_id, status=JobStatus.FAILED, error=f"Unexpected slicing error: {exc}")
    finally:
        import shutil

        shutil.rmtree(work, ignore_errors=True)
