"""Durable job store tests: CRUD, restart-survival, and the slice task.

These prove the persistence seam that the old in-memory dict could not: a job
survives being read back through a brand-new database connection (i.e. a server
restart), and the slice task moves models through object storage.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import config, jobs, slicer, storage
from app.db_models import JobRow
from app.models import JobStatus, SliceOptions, SliceResult


@pytest.fixture()
def queued_job(tmp_path):
    """A persisted, queued job whose input model is in storage."""
    src = tmp_path / "cube.stl"
    src.write_bytes(b"solid cube\nendsolid cube\n")
    key = f"uploads/test-{tmp_path.name}/cube.stl"
    storage.upload_file(key, src)
    return jobs.create_job("cube.stl", key, SliceOptions(filament="pla"))


def test_create_get_list_roundtrip(queued_job):
    got = jobs.get_job(queued_job.id)
    assert got is not None
    assert got.filename == "cube.stl"
    assert got.status is JobStatus.QUEUED
    assert got.options.filament == "pla"
    assert any(j.id == queued_job.id for j in jobs.list_jobs())


def test_job_survives_a_fresh_connection(queued_job):
    # Simulate a server restart: a brand-new engine/session to the same DB must
    # still see the job. (The in-memory dict would lose it here.)
    engine = create_engine(config.DATABASE_URL, connect_args={"check_same_thread": False})
    with sessionmaker(bind=engine)() as s:
        row = s.get(JobRow, queued_job.id)
        assert row is not None and row.status == JobStatus.QUEUED


def test_run_slice_success_uploads_output(queued_job, monkeypatch):
    def fake_slice(inp: Path, out: Path, opts):
        out.write_bytes(b"PK\x03\x04 fake gcode.3mf")
        return SliceResult(estimated_print_seconds=3600, filament_grams=12.5)

    monkeypatch.setattr(slicer, "slice_model", fake_slice)
    jobs.run_slice(queued_job.id)

    done = jobs.get_job(queued_job.id)
    assert done.status is JobStatus.DONE
    assert done.output_path == f"outputs/{queued_job.id}.gcode.3mf"
    assert done.result.estimated_print_seconds == 3600
    # The sliced output is retrievable from storage.
    out = storage.download_to(done.output_path, Path(config.DATA_DIR) / "check.gcode.3mf")
    assert out.read_bytes().startswith(b"PK")


def test_run_slice_failure_sets_error(queued_job, monkeypatch):
    def boom(inp, out, opts):
        raise slicer.SlicerError("missing profile")

    monkeypatch.setattr(slicer, "slice_model", boom)
    jobs.run_slice(queued_job.id)

    failed = jobs.get_job(queued_job.id)
    assert failed.status is JobStatus.FAILED
    assert "missing profile" in failed.error
    assert failed.output_path is None
